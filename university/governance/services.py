from copy import deepcopy
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from employee.models import Employee
from university.people.models import StaffProfile, StaffChange
from university.documents.access import actor_company_id
from .models import UniversityPolicy, PromotionRequest, PromotionEvent


def authorize(actor, permission, company_id):
    if not actor.is_active or not actor.has_perm(permission):
        raise PermissionDenied("The required university HR permission is missing.")
    if not actor.is_superuser and actor_company_id(actor) != company_id:
        raise PermissionDenied("This record belongs to another institution.")


def validate_policy(policy):
    data = policy.configuration
    if not isinstance(data, dict):
        raise ValidationError("Policy configuration must be an object.")
    if policy.module == "promotions":
        months = data.get("minimum_service_months")
        if type(months) is not int or not 0 <= months <= 240:
            raise ValidationError("Promotion minimum service must be 0–240 months.")
        for name in ["teaching_ranks", "non_teaching_ranks"]:
            ranks = data.get(name)
            if (
                not isinstance(ranks, list)
                or not 2 <= len(ranks) <= 30
                or any(
                    not isinstance(rank, str) or not rank.strip() or len(rank) > 100
                    for rank in ranks
                )
                or len(set(ranks)) != len(ranks)
            ):
                raise ValidationError(
                    "Provide unique rank names for each staff category."
                )
        if data.get("automatic_salary_change") is not False:
            raise ValidationError(
                "Automatic salary changes are not permitted by this workflow."
            )
    elif policy.module == "leave":
        if (
            type(data.get("annual_leave_working_days")) is not int
            or not 0 <= data["annual_leave_working_days"] <= 365
        ):
            raise ValidationError(
                "Annual leave must be a configured number of working days."
            )
    elif policy.module == "payroll":
        if not data.get("salary_scales") or not data.get("statutory_tax_tables"):
            raise ValidationError(
                "Configure validated salary scales and current statutory tables before adopting payroll policy."
            )


@transaction.atomic
def adopt_policy(actor, policy_id):
    from base.models import Company

    policy = (
        UniversityPolicy.objects.entire().select_related("company").get(pk=policy_id)
    )
    authorize(actor, "university_governance.adopt_university_policy", policy.company_id)
    Company.objects.select_for_update().get(pk=policy.company_id)
    policy = UniversityPolicy.objects.entire().select_for_update().get(pk=policy_id)
    if policy.adopted_at:
        raise ValidationError(
            "This policy version was already adopted. Create a new version to revise or replace it."
        )
    UniversityPolicy.objects.entire().filter(
        company_id=policy.company_id, module=policy.module, active=True
    ).update(active=False)
    validate_policy(policy)
    policy.active = True
    policy.adopted_by = actor
    policy.adopted_at = timezone.now()
    policy.save(update_fields=["active", "adopted_by", "adopted_at"])
    return policy


def eligibility(employee, snapshot, proposed_rank, effective_date):
    profile = getattr(employee, "university_profile", None)
    work = getattr(employee, "employee_work_info", None)
    if not profile or not work or not work.date_joining or not employee.is_active:
        raise ValidationError(
            "An active staff profile and confirmed joining date are required."
        )
    ranks = snapshot.get(profile.category + "_ranks", [])
    if profile.rank not in ranks or proposed_rank not in ranks:
        raise ValidationError(
            "Choose ranks from the adopted policy for this staff category."
        )
    if ranks.index(proposed_rank) != ranks.index(profile.rank) + 1:
        raise ValidationError(
            "The provisional policy permits promotion to the next rank only."
        )
    months = (
        (effective_date.year - work.date_joining.year) * 12
        + effective_date.month
        - work.date_joining.month
        - (effective_date.day < work.date_joining.day)
    )
    if months < snapshot.get("minimum_service_months", 36):
        raise ValidationError("The minimum service period has not been met.")
    return profile


@transaction.atomic
def request_promotion(
    actor, employee_id, policy_id, proposed_rank, effective_date, evidence
):
    employee = Employee.objects.entire().select_for_update().get(pk=employee_id)
    work = getattr(employee, "employee_work_info", None)
    if not work or not work.company_id_id:
        raise ValidationError("Complete the staff employment record first.")
    authorize(actor, "university_governance.add_promotionrequest", work.company_id_id)
    policy = UniversityPolicy.objects.entire().select_for_update().get(pk=policy_id)
    if (
        not policy.active
        or policy.module != "promotions"
        or policy.company_id != work.company_id_id
    ):
        raise ValidationError(
            "Choose an adopted promotion policy for this institution."
        )
    if not evidence or not evidence.strip() or len(evidence) > 4000:
        raise ValidationError("Provide promotion evidence, at most 4,000 characters.")
    if PromotionRequest.objects.filter(
        employee=employee, status__in=["submitted", "recommended", "approved"]
    ).exists():
        raise ValidationError("This employee already has an open promotion request.")
    snapshot = deepcopy(policy.configuration)
    profile = eligibility(employee, snapshot, proposed_rank, effective_date)
    case = PromotionRequest.objects.create(
        employee=employee,
        policy=policy,
        policy_snapshot=snapshot,
        source_rank=profile.rank,
        proposed_rank=proposed_rank,
        effective_date=effective_date,
        evidence=evidence.strip(),
        requested_by=actor,
    )
    PromotionEvent.objects.create(
        promotion=case,
        actor=actor,
        action="submitted",
        reason="Promotion evidence submitted.",
    )
    return case


@transaction.atomic
def transition_promotion(actor, case_id, action, revision, reason):
    # Match the staff editor's lock order to avoid employee/profile deadlocks.
    employee_id = PromotionRequest.objects.values_list("employee_id", flat=True).get(
        pk=case_id
    )
    employee = Employee.objects.entire().select_for_update().get(pk=employee_id)
    case = (
        PromotionRequest.objects.select_for_update()
        .select_related("policy")
        .get(pk=case_id)
    )
    company_id = employee.employee_work_info.company_id_id
    permissions = {
        "recommend": "review_promotion",
        "approve": "approve_promotion",
        "reject": "approve_promotion",
        "apply": "apply_promotion",
    }
    if action not in permissions:
        raise ValidationError("Unknown promotion action.")
    authorize(actor, "university_governance." + permissions[action], company_id)
    if case.revision != revision:
        raise ValidationError("This request changed. Refresh before trying again.")
    if not reason or not reason.strip() or len(reason) > 1000:
        raise ValidationError("Provide an audit reason, at most 1,000 characters.")
    if action in ["recommend", "approve", "reject"] and actor.pk in {
        case.requested_by_id,
        employee.employee_user_id_id,
    }:
        raise PermissionDenied(
            "You cannot review or approve your own promotion request."
        )
    if action == "recommend":
        if case.status != "submitted":
            raise ValidationError("Only submitted requests can be recommended.")
        case.status = "recommended"
        case.reviewed_by = actor
    elif action == "approve":
        if case.status != "recommended":
            raise ValidationError("An independent recommendation is required first.")
        if actor.pk == case.reviewed_by_id:
            raise PermissionDenied(
                "The reviewer and Registrar approver must be different people."
            )
        case.status = "approved"
        case.approved_by = actor
    elif action == "reject":
        if case.status not in ["submitted", "recommended", "approved"]:
            raise ValidationError("This request can no longer be rejected.")
        case.status = "rejected"
    else:
        if case.status != "approved":
            raise ValidationError("Only an approved promotion can be applied.")
        if case.effective_date > timezone.localdate():
            raise ValidationError("The effective date has not arrived.")
        if not case.policy.active:
            raise ValidationError(
                "The policy was retired; a new promotion review is required."
            )
        profile = StaffProfile.objects.select_for_update().get(employee=employee)
        if profile.rank != case.source_rank:
            raise ValidationError(
                "The staff rank changed; a fresh promotion review is required."
            )
        eligibility(
            employee, case.policy_snapshot, case.proposed_rank, case.effective_date
        )
        profile.rank = case.proposed_rank
        profile.save(update_fields=["rank", "updated_at"])
        StaffChange.objects.create(
            employee=employee,
            actor=actor,
            action="promotion",
            reason=reason,
            changes={
                "rank": {"before": case.source_rank, "after": case.proposed_rank},
                "promotion_id": {"before": None, "after": case.pk},
                "policy_version": {"before": None, "after": case.policy.version},
            },
        )
        case.status = "applied"
    case.revision += 1
    case.save(
        update_fields=["status", "revision", "reviewed_by", "approved_by", "updated_at"]
    )
    PromotionEvent.objects.create(
        promotion=case, actor=actor, action=action, reason=reason.strip()
    )
    return case
