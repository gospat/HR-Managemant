import json
from django.contrib.auth import authenticate
from django.contrib.auth.models import Permission
from django.test import Client, RequestFactory, TestCase
from base.models import Department
from employee.models import Employee, EmployeeWorkInformation
from core.testkit import make_company, make_employee, make_user
from university.people.models import Faculty, StaffChange, StaffProfile


class StaffManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company("University A")
        cls.other = make_company("University B", address="Other campus")
        cls.hr = make_user("records-officer")
        cls.self_employee = make_employee(
            company=cls.company, user=cls.hr, email="hr@records.test"
        )
        cls.staff_user = make_user(
            "lecturer@records.test", password="Testing-Staff-Secret-93284"
        )
        cls.staff = make_employee(
            company=cls.company, user=cls.staff_user, email="lecturer@records.test"
        )
        cls.profile = StaffProfile.objects.create(
            employee=cls.staff, category="teaching", rank="Lecturer II"
        )
        cls.foreign_staff = make_employee(company=cls.other, email="other@records.test")
        cls.foreign_faculty = Faculty.objects.create(
            company=cls.other, code="SCI", name="Other Science"
        )
        cls.department = Department.objects.create(department="Mathematics")
        cls.department.company_id.add(cls.company)
        cls.foreign_department = Department.objects.create(
            department="Foreign Department"
        )
        cls.foreign_department.company_id.add(cls.other)
        cls.hr.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="employee",
                content_type__model="employee",
                codename__in=["view_employee", "change_employee"],
            )
        )
        cls.hr.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="university_people",
                codename__in=["change_staff_status", "view_staff_history"],
            )
        )

    def setUp(self):
        self.client.force_login(
            self.hr, backend="base.auth_backends.CompanyScopedBackend"
        )

    def detail(self, staff=None):
        response = self.client.get(f"/university-api/staff/{(staff or self.staff).pk}/")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def update(self, staff=None, **data):
        staff = staff or self.staff
        payload = {
            "revision": self.detail(staff)["revision"],
            "reason": "Approved HR records correction",
            **data,
        }
        return self.client.patch(
            f"/university-api/staff/{staff.pk}/",
            json.dumps(payload),
            content_type="application/json",
        )

    def status(self, active, staff=None, **overrides):
        staff = staff or self.staff
        payload = {
            "active": active,
            "revision": self.detail(staff)["revision"],
            "reason": "Approved employment status change",
            **overrides,
        }
        return self.client.post(
            f"/university-api/staff/{staff.pk}/status/",
            json.dumps(payload),
            content_type="application/json",
        )

    def test_edit_and_audit_diff(self):
        response = self.update(rank="Lecturer I", department_id=self.department.pk)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["rank"], "Lecturer I")
        self.assertEqual(response.json()["department"], "Mathematics")
        change = StaffChange.objects.get(employee=self.staff)
        self.assertEqual(change.actor_id, self.hr.pk)
        self.assertEqual(change.reason, "Approved HR records correction")
        self.assertEqual(
            change.changes["rank"], {"before": "Lecturer II", "after": "Lecturer I"}
        )
        self.assertNotIn("email", change.changes)

    def test_stale_update_is_rejected_without_overwriting(self):
        old_revision = self.detail()["revision"]
        self.assertEqual(self.update(rank="Lecturer I").status_code, 200)
        response = self.update(rank="Professor", revision=old_revision)
        self.assertEqual(response.status_code, 409)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.rank, "Lecturer I")
        self.assertEqual(StaffChange.objects.filter(employee=self.staff).count(), 1)

    def test_change_in_legacy_screen_also_invalidates_revision(self):
        revision = self.detail()["revision"]
        Employee.objects.entire().filter(pk=self.staff.pk).update(
            phone="+2348099999999"
        )
        response = self.update(rank="Professor", revision=revision)
        self.assertEqual(response.status_code, 409)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.phone, "+2348099999999")
        self.assertFalse(StaffChange.objects.filter(employee=self.staff).exists())

    def test_foreign_staff_and_history_are_not_disclosed(self):
        for suffix in ["", "history/"]:
            self.assertEqual(
                self.client.get(
                    f"/university-api/staff/{self.foreign_staff.pk}/{suffix}"
                ).status_code,
                404,
            )
        response = self.client.patch(
            f"/university-api/staff/{self.foreign_staff.pk}/",
            json.dumps(
                {
                    "revision": "0" * 64,
                    "reason": "Unauthorized change",
                    "rank": "Professor",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_foreign_faculty_rolls_back_all_changes(self):
        response = self.update(first_name="Changed", faculty_id=self.foreign_faculty.pk)
        self.assertEqual(response.status_code, 400)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.employee_first_name, "Test")
        self.assertFalse(StaffChange.objects.filter(employee=self.staff).exists())

    def test_foreign_department_is_rejected(self):
        self.assertEqual(
            self.update(department_id=self.foreign_department.pk).status_code, 400
        )

    def test_identity_institution_and_access_fields_cannot_be_smuggled(self):
        for data in [
            {"email": "hijack@records.test"},
            {"company_id": self.other.pk},
            {"active": False},
            {"is_superuser": True},
        ]:
            self.assertEqual(self.update(**data).status_code, 400)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.email, "lecturer@records.test")
        self.assertTrue(self.staff.is_active)

    def test_reason_is_required(self):
        self.assertEqual(self.update(rank="Professor", reason="").status_code, 400)
        self.assertEqual(self.status(False, reason="").status_code, 400)

    def test_empty_edit_does_not_emit_an_event(self):
        self.assertEqual(self.update().status_code, 400)
        self.assertFalse(StaffChange.objects.filter(employee=self.staff).exists())

    def test_no_change_edit_preserves_revision(self):
        revision = self.detail()["revision"]
        response = self.update(rank="Lecturer II")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["revision"], revision)
        self.assertFalse(StaffChange.objects.filter(employee=self.staff).exists())

    def test_archive_revokes_password_authentication_and_existing_session(self):
        staff_client = Client()
        staff_client.force_login(
            self.staff_user, backend="base.auth_backends.CompanyScopedBackend"
        )
        self.assertTrue(
            staff_client.get("/university-api/session/").json()["authenticated"]
        )
        response = self.status(False)
        self.assertEqual(response.status_code, 200, response.content)
        self.staff.refresh_from_db()
        self.staff_user.refresh_from_db()
        self.assertFalse(self.staff.is_active)
        self.assertFalse(self.staff_user.is_active)
        request = RequestFactory().post("/login/")
        self.assertIsNone(
            authenticate(
                request,
                username=self.staff_user.username,
                password="Testing-Staff-Secret-93284",
            )
        )
        self.assertFalse(
            staff_client.get("/university-api/session/").json()["authenticated"]
        )
        self.assertEqual(
            StaffChange.objects.get(employee=self.staff).action, "archived"
        )

    def test_restore_record_alone_does_not_restore_login(self):
        self.assertEqual(self.status(False).status_code, 200)
        response = self.status(True)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["active"])
        self.assertFalse(response.json()["login_active"])

    def test_restoring_login_requires_separate_permission(self):
        self.assertEqual(self.status(False).status_code, 200)
        self.assertEqual(self.status(True, restore_login=True).status_code, 403)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_active)

    def test_authorized_explicit_restore_allows_authentication(self):
        self.hr.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="university_people",
                codename="restore_staff_login",
            )
        )
        self.assertEqual(self.status(False).status_code, 200)
        response = self.status(True, restore_login=True)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["login_active"])
        request = RequestFactory().post("/login/")
        self.assertIsNotNone(
            authenticate(
                request,
                username=self.staff_user.username,
                password="Testing-Staff-Secret-93284",
            )
        )

    def test_unconfigured_password_cannot_be_activated_by_status_change(self):
        self.hr.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="university_people",
                codename="restore_staff_login",
            )
        )
        self.staff_user.set_unusable_password()
        self.staff_user.save()
        self.assertEqual(self.status(False).status_code, 200)
        self.assertEqual(self.status(True, restore_login=True).status_code, 400)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_active)

    def test_cannot_archive_self(self):
        self.assertEqual(self.status(False, staff=self.self_employee).status_code, 400)

    def test_cannot_archive_privileged_account(self):
        self.staff_user.is_staff = True
        self.staff_user.save()
        self.assertEqual(self.status(False).status_code, 403)

    def test_manager_with_responsibilities_cannot_be_archived(self):
        dependent = make_employee(company=self.company, email="dependent@records.test")
        EmployeeWorkInformation.objects.filter(employee_id=dependent).update(
            reporting_manager_id=self.staff
        )
        self.assertEqual(self.status(False).status_code, 400)
        self.staff.refresh_from_db()
        self.staff_user.refresh_from_db()
        self.assertTrue(self.staff.is_active)
        self.assertTrue(self.staff_user.is_active)

    def test_edits_do_not_undo_separate_login_revocation(self):
        self.staff_user.is_active = False
        self.staff_user.save()
        self.assertEqual(self.update(rank="Lecturer I").status_code, 200)
        self.staff_user.refresh_from_db()
        self.assertFalse(self.staff_user.is_active)

    def test_history_requires_its_own_permission(self):
        self.hr.user_permissions.remove(
            Permission.objects.get(
                content_type__app_label="university_people",
                codename="view_staff_history",
            )
        )
        self.assertEqual(
            self.client.get(
                f"/university-api/staff/{self.staff.pk}/history/"
            ).status_code,
            403,
        )

    def test_history_contains_actor_reason_and_changes(self):
        self.assertEqual(self.update(rank="Lecturer I").status_code, 200)
        response = self.client.get(f"/university-api/staff/{self.staff.pk}/history/")
        self.assertEqual(response.status_code, 200)
        event = response.json()["results"][0]
        self.assertEqual(event["actor"], "records-officer")
        self.assertEqual(event["reason"], "Approved HR records correction")
        self.assertEqual(event["changes"]["rank"]["after"], "Lecturer I")
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_edit_permission_does_not_grant_status_or_history_permissions(self):
        self.hr.user_permissions.remove(
            *Permission.objects.filter(content_type__app_label="university_people")
        )
        self.assertEqual(self.update(rank="Lecturer I").status_code, 200)
        self.assertEqual(self.status(False).status_code, 403)
        self.assertEqual(
            self.client.get(
                f"/university-api/staff/{self.staff.pk}/history/"
            ).status_code,
            403,
        )

    def test_read_only_hr_cannot_edit(self):
        self.hr.user_permissions.remove(
            Permission.objects.get(
                content_type__app_label="employee",
                content_type__model="employee",
                codename="change_employee",
            )
        )
        self.assertEqual(self.update(rank="Lecturer I").status_code, 403)

    def test_mutations_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.hr, backend="base.auth_backends.CompanyScopedBackend")
        payload = {
            "revision": self.detail()["revision"],
            "reason": "Validated reason",
            "rank": "Lecturer I",
        }
        self.assertEqual(
            client.patch(
                f"/university-api/staff/{self.staff.pk}/",
                json.dumps(payload),
                content_type="application/json",
            ).status_code,
            403,
        )
        self.assertEqual(
            client.post(
                f"/university-api/staff/{self.staff.pk}/status/",
                json.dumps({"active": False, **payload}),
                content_type="application/json",
            ).status_code,
            403,
        )
