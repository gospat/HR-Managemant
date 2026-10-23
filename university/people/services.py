import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework.exceptions import PermissionDenied
from base.models import Company, Department
from employee.models import Employee, EmployeeWorkInformation
from horilla_auth.models import HorillaUser
from .models import Faculty, StaffProfile, StaffChange


def company_scope(user):
    """Never infer authorization from client-selected company or session filters."""
    if user.is_superuser:
        return None
    return (
        EmployeeWorkInformation.objects.filter(employee_id__employee_user_id=user)
        .values_list("company_id_id", flat=True)
        .first()
    )


def scoped_employees(user):
    qs = Employee.objects.entire().select_related(
        "employee_work_info__department_id", "university_profile__faculty"
    )
    if not user.is_superuser:
        company_id = company_scope(user)
        qs = (
            qs.filter(employee_work_info__company_id_id=company_id)
            if company_id
            else qs.none()
        )
    return qs


@transaction.atomic
def create_staff(*, actor, data):
    company_id = data["company_id"]
    if not actor.is_superuser and company_scope(actor) != company_id:
        raise PermissionDenied("You cannot create staff in another institution.")
    company = Company.objects.get(pk=company_id)
    department_id = data.get("department_id")
    if (
        department_id
        and not Department.objects.entire()
        .filter(pk=department_id, company_id=company)
        .exists()
    ):
        raise ValidationError(
            {"department_id": "Choose a department in this institution."}
        )
    faculty_id = data.get("faculty_id")
    if (
        faculty_id
        and not Faculty.objects.filter(pk=faculty_id, company=company).exists()
    ):
        raise ValidationError({"faculty_id": "Choose a faculty in this institution."})
    # Do not silently attach a new employee to an existing login or create a
    # predictable password. Activation is a separate administrator action.
    if HorillaUser.objects.filter(username=data["email"]).exists():
        raise ValidationError({"email": "A login already uses this email address."})
    user = HorillaUser.objects.create_user(
        username=data["email"], email=data["email"], password=None
    )
    employee = Employee(
        employee_first_name=data["first_name"],
        employee_last_name=data["last_name"],
        email=data["email"],
        phone=data["phone"],
        badge_id=data["staff_number"],
        employee_user_id=user,
    )
    employee.save()
    EmployeeWorkInformation.objects.update_or_create(
        employee_id=employee,
        defaults={"company_id": company, "department_id_id": department_id},
    )
    profile = StaffProfile(
        employee=employee,
        category=data["category"],
        faculty_id=faculty_id,
        rank=data["rank"],
    )
    profile.full_clean()
    profile.save()
    StaffChange.objects.create(employee=employee, actor=actor, action="created")
    return employee


def staff_record(employee):
    work = getattr(employee, "employee_work_info", None)
    profile = getattr(employee, "university_profile", None)
    return {
        "id": employee.pk,
        "name": " ".join(
            filter(None, [employee.employee_first_name, employee.employee_last_name])
        ),
        "email": employee.email,
        "staff_number": employee.badge_id,
        "department": (
            str(work.department_id) if work and work.department_id_id else None
        ),
        "category": profile.category if profile else None,
        "faculty": profile.faculty.name if profile and profile.faculty_id else None,
        "rank": profile.rank if profile else "",
        "active": employee.is_active,
    }


class StaleStaffRecord(Exception):
    """A client attempted to overwrite a newer change."""


def staff_revision(employee):
    """Include actual shared Horilla fields so legacy-screen edits also conflict."""
    work = getattr(employee, "employee_work_info", None)
    profile = getattr(employee, "university_profile", None)
    user = employee.employee_user_id if employee.employee_user_id_id else None
    state = {
        "employee": [
            employee.employee_first_name,
            employee.employee_last_name,
            employee.email,
            employee.phone,
            employee.badge_id,
            employee.is_active,
        ],
        "work": [work.company_id_id, work.department_id_id] if work else None,
        "profile": (
            [profile.category, profile.faculty_id, profile.rank] if profile else None
        ),
        "login": (
            [
                user.is_active,
                user.is_staff,
                user.is_superuser,
                user.has_usable_password(),
            ]
            if user
            else None
        ),
        "event": StaffChange.objects.filter(employee=employee)
        .order_by("-pk")
        .values_list("pk", flat=True)
        .first(),
    }
    return hashlib.sha256(
        json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def staff_detail(employee, actor=None):
    work = getattr(employee, "employee_work_info", None)
    profile = getattr(employee, "university_profile", None)
    return {
        **staff_record(employee),
        "first_name": employee.employee_first_name,
        "last_name": employee.employee_last_name or "",
        "phone": employee.phone,
        "company_id": work.company_id_id if work else None,
        "department_id": work.department_id_id if work else None,
        "faculty_id": profile.faculty_id if profile else None,
        "revision": staff_revision(employee),
        "login_active": (
            employee.employee_user_id.is_active
            if employee.employee_user_id_id
            else False
        ),
        "can_change_status": bool(
            employee.employee_user_id_id
            and (actor is None or employee.employee_user_id_id != actor.pk)
            and not (
                employee.employee_user_id.is_superuser
                or employee.employee_user_id.is_staff
            )
        ),
    }


def locked_staff(actor, employee_id, revision):
    employee = Employee.objects.entire().select_for_update().get(pk=employee_id)
    work = EmployeeWorkInformation.objects.select_for_update().get(employee_id=employee)
    if not actor.is_superuser and work.company_id_id != company_scope(actor):
        raise PermissionDenied("Staff record is outside your institution.")
    if employee.employee_user_id_id:
        employee.employee_user_id = HorillaUser.objects.select_for_update().get(
            pk=employee.employee_user_id_id
        )
    profile = StaffProfile.objects.select_for_update().filter(employee=employee).first()
    if profile is not None:
        employee.university_profile = profile
    if revision != staff_revision(employee):
        raise StaleStaffRecord()
    return employee, work


def validate_assignments(company_id, data):
    department_id = data.get("department_id")
    if (
        department_id
        and not Department.objects.entire()
        .filter(pk=department_id, company_id=company_id)
        .exists()
    ):
        raise ValidationError(
            {"department_id": "Choose a department in this institution."}
        )
    faculty_id = data.get("faculty_id")
    if (
        faculty_id
        and not Faculty.objects.entire()
        .filter(pk=faculty_id, company_id=company_id)
        .exists()
    ):
        raise ValidationError({"faculty_id": "Choose a faculty in this institution."})


@transaction.atomic
def update_staff(*, actor, employee_id, data):
    employee, work = locked_staff(actor, employee_id, data["revision"])
    before = staff_detail(employee)
    validate_assignments(work.company_id_id, data)
    for key, field in {
        "first_name": "employee_first_name",
        "last_name": "employee_last_name",
        "phone": "phone",
        "staff_number": "badge_id",
    }.items():
        if key in data:
            setattr(employee, field, data[key])
    employee.save()
    if "department_id" in data:
        work.department_id_id = data["department_id"]
        work.save(update_fields=["department_id"])
    profile = StaffProfile.objects.filter(employee=employee).first()
    if profile is None:
        if not data.get("category"):
            raise ValidationError(
                {
                    "category": "Classify this staff member before saving university details."
                }
            )
        profile = StaffProfile(employee=employee, category=data["category"])
    if "rank" in data and data["rank"] != profile.rank:
        from university.governance.models import UniversityPolicy

        if (
            not actor.is_superuser
            and UniversityPolicy.objects.entire()
            .filter(company_id=work.company_id_id, module="promotions", active=True)
            .exists()
        ):
            raise ValidationError(
                {
                    "rank": "Use the promotion workflow to change rank under an adopted policy."
                }
            )
    for field in ["category", "faculty_id", "rank"]:
        if field in data:
            setattr(profile, field, data[field])
    profile.full_clean()
    profile.save()
    # Reload related objects so the response and diff reflect committed fields,
    # not OneToOne objects cached before the write.
    employee = scoped_employees(actor).get(pk=employee.pk)
    after = staff_detail(employee)
    fields = [
        "first_name",
        "last_name",
        "phone",
        "staff_number",
        "department_id",
        "faculty_id",
        "category",
        "rank",
    ]
    changes = {
        field: {"before": before[field], "after": after[field]}
        for field in fields
        if before[field] != after[field]
    }
    for key, label in [("department_id", "department"), ("faculty_id", "faculty")]:
        if key in changes:
            changes[key]["before_label"] = before[label] or "Not assigned"
            changes[key]["after_label"] = after[label] or "Not assigned"
    if changes:
        StaffChange.objects.create(
            employee=employee,
            actor=actor,
            action="updated",
            reason=data["reason"],
            changes=changes,
        )
    return employee


@transaction.atomic
def change_staff_status(*, actor, employee_id, data):
    employee, _ = locked_staff(actor, employee_id, data["revision"])
    if employee.employee_user_id_id == actor.pk:
        raise ValidationError("You cannot archive or restore your own account here.")
    if not employee.employee_user_id_id:
        raise ValidationError(
            "This staff record has no linked account. Contact administration."
        )
    user = employee.employee_user_id
    if user.is_superuser or user.is_staff:
        raise PermissionDenied(
            "Privileged accounts must be managed through administration."
        )
    if employee.is_active == data["active"]:
        raise ValidationError("This record already has the requested status.")
    if not data["active"] and employee.get_archive_condition() is not False:
        raise ValidationError(
            "Reassign this staff member’s management and workflow responsibilities before archiving."
        )
    if data["restore_login"]:
        if not actor.has_perm("university_people.restore_staff_login"):
            raise PermissionDenied(
                "Separate permission is required to restore login access."
            )
        if not user.has_usable_password():
            raise ValidationError(
                "A secure password must be configured before restoring login access."
            )
    before_active, before_login = employee.is_active, user.is_active
    employee.is_active = data["active"]
    employee.save(update_fields=["is_active"])
    # Restoring a staff record alone must never undo a separate access revocation.
    if not employee.is_active:
        user.is_active = False
    elif data["restore_login"]:
        user.is_active = True
    user.save(update_fields=["is_active"])
    StaffChange.objects.create(
        employee=employee,
        actor=actor,
        action="restored" if employee.is_active else "archived",
        reason=data["reason"],
        changes={
            "active": {"before": before_active, "after": employee.is_active},
            "login_active": {"before": before_login, "after": user.is_active},
        },
    )
    return scoped_employees(actor).get(pk=employee.pk)
