"""10,000-record directory correctness/query-growth check, not a peak-load claim."""

import json
import time
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory, force_authenticate
from employee.models import Employee, EmployeeWorkInformation
from core.testkit import make_company, make_employee
from university.people.models import StaffProfile
from university.people.views import StaffView


class LargeDirectoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company("Synthetic scale test university")
        cls.hr = make_employee(
            company=cls.company, email="hr@scale.test"
        ).employee_user_id
        cls.hr.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="employee", codename="view_employee"
            )
        )
        Employee.objects.bulk_create(
            [
                Employee(
                    employee_first_name="Synthetic",
                    employee_last_name=f"Staff {i:05}",
                    email=f"staff{i}@scale.test",
                    phone="08000000000",
                    badge_id=f"BELLS-SCALE-{i:05}",
                )
                for i in range(10000)
            ],
            batch_size=500,
        )
        records = list(
            Employee.objects.entire()
            .filter(badge_id__startswith="BELLS-SCALE-")
            .order_by("badge_id")
        )
        EmployeeWorkInformation.objects.bulk_create(
            [
                EmployeeWorkInformation(employee_id=employee, company_id=cls.company)
                for employee in records
            ],
            batch_size=500,
        )
        StaffProfile.objects.bulk_create(
            [
                StaffProfile(
                    employee=employee,
                    category="teaching" if i % 2 == 0 else "non_teaching",
                    rank="Synthetic rank",
                )
                for i, employee in enumerate(records)
            ],
            batch_size=500,
        )

    def test_pagination_search_and_category_at_ten_thousand_records(self):
        self.hr.has_perm("employee.view_employee")
        factory = APIRequestFactory()
        cases = [
            ({"q": "BELLS-SCALE-"}, 10000, 25),
            ({"q": "BELLS-SCALE-", "page": 400}, 10000, 25),
            ({"q": "BELLS-SCALE-", "category": "teaching"}, 5000, 25),
            ({"q": "BELLS-SCALE-09999"}, 1, 1),
        ]
        timings = []
        for parameters, count, rows in cases:
            request = factory.get("/university-api/staff/", parameters)
            force_authenticate(request, user=self.hr)
            start = time.perf_counter()
            with CaptureQueriesContext(connection) as captured:
                response = StaffView.as_view()(request)
                response.render()
            timings.append(round((time.perf_counter() - start) * 1000, 2))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], count)
            self.assertEqual(len(response.data["results"]), rows)
            self.assertLessEqual(
                len(captured), 6, "Directory queries must not grow per staff row"
            )
        print(
            json.dumps(
                {
                    "synthetic_staff": 10000,
                    "directory_case_ms": timings,
                    "peak_concurrency_tested": False,
                }
            )
        )
