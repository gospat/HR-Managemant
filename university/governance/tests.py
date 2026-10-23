from copy import deepcopy
from datetime import date
from io import StringIO
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.management import call_command
from django.test import TestCase, Client
from django.utils import timezone
from horilla.testkit import make_company, make_employee, make_user
from employee.models import EmployeeWorkInformation
from university.people.models import StaffProfile, StaffChange
from .defaults import DEFAULTS, POLICY_VERSION
from .models import UniversityPolicy, PromotionRequest, PromotionEvent
from .services import request_promotion, transition_promotion, adopt_policy


class PromotionWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company("Governance University")
        cls.other = make_company("Other institution")
        cls.staff = make_employee(
            company=cls.company,
            email="staff@governance.test",
            date_joining=date(2018, 1, 1),
        )
        StaffProfile.objects.create(
            employee=cls.staff, category="teaching", rank="Lecturer II"
        )
        cls.creator = cls.actor(
            "creator",
            cls.company,
            [
                "add_promotionrequest",
                "apply_promotion",
                "view_promotionrequest",
                "view_universitypolicy",
                "review_promotion",
            ],
        )
        cls.reviewer = cls.actor(
            "reviewer",
            cls.company,
            ["review_promotion", "approve_promotion", "view_promotionrequest"],
        )
        cls.registrar = cls.actor(
            "registrar", cls.company, ["approve_promotion", "adopt_university_policy"]
        )
        cls.root = make_user("governance-root", is_superuser=True)
        cls.policy = UniversityPolicy.objects.create(
            company=cls.company,
            module="promotions",
            version=POLICY_VERSION,
            configuration=deepcopy(DEFAULTS["promotions"]),
        )
        adopt_policy(cls.root, cls.policy.pk)

    @classmethod
    def actor(cls, name, company, codes):
        user = make_user("promotion-" + name)
        make_employee(company=company, email=name + "@governance.test", user=user)
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="university_governance", codename__in=codes
            )
        )
        return user

    def submit(self, **kwargs):
        values = dict(
            actor=self.creator,
            employee_id=self.staff.pk,
            policy_id=self.policy.pk,
            proposed_rank="Lecturer I",
            effective_date=timezone.localdate(),
            evidence="Teaching record and peer-reviewed evidence attached in personnel record.",
        )
        values.update(kwargs)
        return request_promotion(**values)

    def approve(self):
        case = self.submit()
        case = transition_promotion(
            self.reviewer,
            case.pk,
            "recommend",
            case.revision,
            "Evidence reviewed by committee.",
        )
        return transition_promotion(
            self.registrar,
            case.pk,
            "approve",
            case.revision,
            "Approved subject to the adopted provisional policy.",
        )

    def test_four_eyes_workflow_applies_once_and_preserves_audit(self):
        case = self.approve()
        case = transition_promotion(
            self.creator, case.pk, "apply", case.revision, "Approved promotion applied."
        )
        self.assertEqual(case.status, "applied")
        self.assertEqual(
            StaffProfile.objects.get(employee=self.staff).rank, "Lecturer I"
        )
        self.assertEqual(PromotionEvent.objects.filter(promotion=case).count(), 4)
        self.assertEqual(
            StaffChange.objects.get(employee=self.staff).action, "promotion"
        )
        with self.assertRaises(ValidationError):
            transition_promotion(
                self.creator,
                case.pk,
                "apply",
                case.revision,
                "Duplicate action blocked.",
            )

    def test_unauthorized_cross_institution_and_duplicate_cases_are_blocked(self):
        outsider = self.actor(
            "outsider", self.other, ["add_promotionrequest", "approve_promotion"]
        )
        with self.assertRaises(PermissionDenied):
            self.submit(actor=outsider)
        self.submit()
        with self.assertRaises(ValidationError):
            self.submit()

    def test_requester_reviewer_and_approver_must_be_independent(self):
        case = self.submit()
        with self.assertRaises(PermissionDenied):
            transition_promotion(
                self.creator, case.pk, "recommend", case.revision, "Self review."
            )
        case = transition_promotion(
            self.reviewer, case.pk, "recommend", case.revision, "Independent review."
        )
        with self.assertRaises(PermissionDenied):
            transition_promotion(
                self.reviewer, case.pk, "approve", case.revision, "Self approval."
            )

    def test_stale_revision_and_missing_reason_do_not_change_status(self):
        case = self.submit()
        for revision, reason in [(0, "Old form."), (case.revision, "")]:
            with self.assertRaises(ValidationError):
                transition_promotion(
                    self.reviewer, case.pk, "recommend", revision, reason
                )
        case.refresh_from_db()
        self.assertEqual(case.status, "submitted")

    def test_invalid_rank_insufficient_service_and_inactive_staff_are_blocked(self):
        with self.assertRaises(ValidationError):
            self.submit(proposed_rank="Professor")
        EmployeeWorkInformation.objects.filter(employee_id=self.staff).update(
            date_joining=timezone.localdate()
        )
        with self.assertRaises(ValidationError):
            self.submit()
        self.staff.is_active = False
        self.staff.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            self.submit()

    def test_future_effective_date_and_changed_rank_cannot_be_applied(self):
        case = self.approve()
        case.effective_date = date(2099, 1, 1)
        case.save(update_fields=["effective_date"])
        with self.assertRaises(ValidationError):
            transition_promotion(
                self.creator, case.pk, "apply", case.revision, "Too early."
            )
        case.effective_date = timezone.localdate()
        case.save(update_fields=["effective_date"])
        StaffProfile.objects.filter(employee=self.staff).update(rank="Senior Lecturer")
        with self.assertRaises(ValidationError):
            transition_promotion(
                self.creator, case.pk, "apply", case.revision, "Stale rank."
            )

    def test_policy_seeding_is_idempotent_and_does_not_claim_approval(self):
        call_command(
            "seed_university_policies", company=self.company.pk, stdout=StringIO()
        )
        call_command(
            "seed_university_policies", company=self.company.pk, stdout=StringIO()
        )
        self.assertEqual(
            UniversityPolicy.objects.entire().filter(company=self.company).count(), 5
        )
        leave = UniversityPolicy.objects.entire().get(
            company=self.company, module="leave"
        )
        self.assertFalse(leave.active)
        self.assertTrue(leave.provisional)
        self.assertIsNone(leave.adopted_by)
        payroll = UniversityPolicy.objects.entire().get(
            company=self.company, module="payroll"
        )
        with self.assertRaises(ValidationError):
            adopt_policy(self.root, payroll.pk)

    def test_api_csrf_privilege_injection_scope_and_malformed_payloads(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(
            self.creator, backend="base.auth_backends.CompanyScopedBackend"
        )
        self.assertEqual(
            client.post(
                "/university-api/promotions/", {}, content_type="application/json"
            ).status_code,
            403,
        )
        token = client.get("/university-api/session/").json()["csrf"]
        self.assertEqual(
            client.post(
                "/university-api/promotions/",
                {"status": "approved"},
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
            ).status_code,
            400,
        )
        self.assertEqual(
            client.post(
                "/university-api/promotions/",
                [],
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
            ).status_code,
            400,
        )
        response = client.get("/university-api/promotions/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])

    def test_retired_policy_cannot_apply_an_approved_case(self):
        case = self.approve()
        UniversityPolicy.objects.entire().filter(pk=self.policy.pk).update(active=False)
        with self.assertRaises(ValidationError):
            transition_promotion(
                self.creator, case.pk, "apply", case.revision, "Policy retired."
            )
        self.assertEqual(
            StaffProfile.objects.get(employee=self.staff).rank, "Lecturer II"
        )

    def test_authenticated_api_creates_case_and_exposes_only_its_institution(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(
            self.creator, backend="base.auth_backends.CompanyScopedBackend"
        )
        token = client.get("/university-api/session/").json()["csrf"]
        response = client.post(
            "/university-api/promotions/",
            {
                "employee_id": self.staff.pk,
                "policy_id": self.policy.pk,
                "proposed_rank": "Lecturer I",
                "effective_date": timezone.localdate().isoformat(),
                "evidence": "Verified synthetic teaching evidence.",
            },
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["status"], "submitted")
        policies = client.get("/university-api/policies/").json()["results"]
        self.assertTrue(policies)
        self.assertTrue(all(row["company_id"] == self.company.pk for row in policies))

    def test_staff_editor_cannot_bypass_promotion_policy(self):
        from university.people.services import update_staff, staff_revision

        with self.assertRaises(ValidationError):
            update_staff(
                actor=self.creator,
                employee_id=self.staff.pk,
                data={
                    "revision": staff_revision(self.staff),
                    "reason": "Attempted direct promotion.",
                    "rank": "Professor",
                },
            )
        self.assertEqual(
            StaffProfile.objects.get(employee=self.staff).rank, "Lecturer II"
        )

    def test_adoption_identity_cannot_be_overwritten_by_re_adopting_a_version(self):
        with self.assertRaises(ValidationError):
            adopt_policy(self.registrar, self.policy.pk)
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.adopted_by_id, self.root.pk)
