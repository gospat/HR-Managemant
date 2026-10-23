import json
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from horilla.testkit import make_company, make_employee, make_user
from employee.models import Employee
from hr_auth.models import HorillaUser
from university.people.models import Faculty, StaffChange, StaffProfile


class StaffDirectoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company("University A", country="Nigeria")
        cls.other_company = make_company(
            "University B", address="Other campus", country="Nigeria"
        )
        cls.admin = make_user("hr-admin", is_superuser=True)
        cls.hr = make_user("hr-officer")
        make_employee(
            company=cls.company, user=cls.admin, email="admin@university.test"
        )
        cls.hr_employee = make_employee(
            company=cls.company, user=cls.hr, email="hr@university.test"
        )
        cls.other_employee = make_employee(
            company=cls.other_company, email="private@other.test"
        )
        cls.hr.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="employee",
                content_type__model="employee",
                codename__in=["view_employee", "add_employee"],
            )
        )
        cls.faculty = Faculty.objects.create(
            company=cls.company, name="Science", code="SCI"
        )

    def setUp(self):
        self.client.force_login(
            self.hr, backend="base.auth_backends.CompanyScopedBackend"
        )

    def payload(self, **overrides):
        data = {
            "first_name": "Amina",
            "last_name": "Okafor",
            "email": "amina@university.test",
            "phone": "+2348012345678",
            "staff_number": "UNI-001",
            "category": "teaching",
            "company_id": self.company.pk,
            "faculty_id": self.faculty.pk,
            "rank": "Lecturer II",
        }
        data.update(overrides)
        return data

    def post(self, data):
        return self.client.post(
            "/university-api/staff/", json.dumps(data), content_type="application/json"
        )

    def test_anonymous_cannot_read_staff(self):
        self.client.logout()
        response = self.client.get("/university-api/staff/")
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("private@other.test", response.content.decode())

    def test_authenticated_staff_without_hr_permission_is_denied(self):
        user = self.other_employee.employee_user_id
        user.is_new_employee = False
        user.save(update_fields=["is_new_employee"])
        self.client.force_login(
            self.other_employee.employee_user_id,
            backend="base.auth_backends.CompanyScopedBackend",
        )
        self.assertEqual(self.client.get("/university-api/staff/").status_code, 403)
        self.assertEqual(self.post(self.payload()).status_code, 403)

    def test_hr_sees_only_own_institution(self):
        response = self.client.get("/university-api/staff/")
        self.assertEqual(response.status_code, 200)
        ids = [row["id"] for row in response.json()["results"]]
        self.assertIn(self.hr_employee.pk, ids)
        self.assertNotIn(self.other_employee.pk, ids)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_client_selected_company_does_not_expand_scope(self):
        session = self.client.session
        session["selected_company"] = str(self.other_company.pk)
        session.save()
        response = self.client.get(
            "/university-api/staff/", {"company_id": self.other_company.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            self.other_employee.pk, [row["id"] for row in response.json()["results"]]
        )

    def test_create_teaching_staff_and_audit_without_password(self):
        response = self.post(self.payload())
        self.assertEqual(response.status_code, 201, response.content)
        employee = Employee.objects.entire().get(pk=response.json()["id"])
        self.assertEqual(employee.university_profile.category, "teaching")
        self.assertEqual(employee.employee_work_info.company_id_id, self.company.pk)
        self.assertFalse(employee.employee_user_id.has_usable_password())
        self.assertTrue(
            StaffChange.objects.filter(
                employee=employee, actor=self.hr, action="created"
            ).exists()
        )

    def test_create_non_teaching_staff(self):
        response = self.post(
            self.payload(category="non_teaching", rank="Administrative Officer")
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["category"], "non_teaching")

    def test_foreign_institution_create_is_denied_and_atomic(self):
        before = HorillaUser.objects.count()
        response = self.post(self.payload(company_id=self.other_company.pk))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(HorillaUser.objects.count(), before)
        self.assertFalse(
            Employee.objects.entire().filter(email="amina@university.test").exists()
        )

    def test_foreign_faculty_is_rejected(self):
        other_faculty = Faculty.objects.create(
            company=self.other_company, name="Arts", code="ART"
        )
        response = self.post(self.payload(faculty_id=other_faculty.pk))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            HorillaUser.objects.filter(username="amina@university.test").exists()
        )

    def test_duplicate_staff_number_rolls_back_login_and_profile(self):
        self.assertEqual(self.post(self.payload()).status_code, 201)
        before = HorillaUser.objects.count()
        response = self.post(self.payload(email="another@university.test"))
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(HorillaUser.objects.count(), before)
        self.assertEqual(StaffProfile.objects.count(), 1)

    def test_category_filter_and_search(self):
        self.assertEqual(self.post(self.payload()).status_code, 201)
        response = self.client.get(
            "/university-api/staff/", {"q": "UNI-001", "category": "teaching"}
        )
        self.assertEqual(response.json()["count"], 1)
        response = self.client.get(
            "/university-api/staff/", {"category": "non_teaching"}
        )
        self.assertEqual(response.json()["count"], 0)
        self.assertEqual(
            self.client.get(
                "/university-api/staff/", {"category": "invalid"}
            ).status_code,
            400,
        )

    def test_options_do_not_include_other_institution(self):
        response = self.client.get("/university-api/staff/options/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["id"] for row in response.json()["companies"]], [self.company.pk]
        )

    def test_post_requires_csrf_even_with_valid_session(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.hr, backend="base.auth_backends.CompanyScopedBackend")
        response = client.post(
            "/university-api/staff/",
            json.dumps(self.payload()),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        token = client.get("/university-api/session/").json()["csrf"]
        response = client.post(
            "/university-api/staff/",
            json.dumps(self.payload()),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 201, response.content)

    def test_directory_user_with_no_institution_gets_no_records(self):
        user = make_user("orphan-hr")
        make_employee(company=None, user=user, email="orphan@university.test")
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="employee",
                content_type__model="employee",
                codename="view_employee",
            )
        )
        self.client.force_login(user, backend="base.auth_backends.CompanyScopedBackend")
        response = self.client.get("/university-api/staff/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_existing_login_is_not_silently_linked(self):
        user = make_user("amina@university.test")
        response = self.post(self.payload())
        self.assertEqual(response.status_code, 400)
        user.refresh_from_db()
        self.assertFalse(hasattr(user, "employee_get"))

    def test_missing_required_data_does_not_create_partial_records(self):
        before = HorillaUser.objects.count()
        response = self.post({"category": "teaching"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(HorillaUser.objects.count(), before)

    def test_logout_requires_csrf_and_ends_session(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.hr, backend="base.auth_backends.CompanyScopedBackend")
        self.assertEqual(client.delete("/university-api/session/").status_code, 403)
        token = client.get("/university-api/session/").json()["csrf"]
        self.assertEqual(
            client.delete(
                "/university-api/session/", HTTP_X_CSRFTOKEN=token
            ).status_code,
            204,
        )
        self.assertEqual(client.get("/university-api/staff/").status_code, 403)
