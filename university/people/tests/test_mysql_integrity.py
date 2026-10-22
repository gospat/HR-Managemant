from datetime import date
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from base.models import DefaultExportPermission, Holidays
from horilla.testkit import make_company, make_employee
from employee.models import Employee


class MySQLIntegrityTests(TestCase):
    def test_target_database_is_mysql(self):
        self.assertEqual(connection.vendor, "mysql")

    def test_global_holiday_unique_index_rejects_duplicate_bulk_insert(self):
        values = dict(
            name="New Year",
            start_date=date(2030, 1, 1),
            end_date=date(2030, 1, 1),
            company_id=None,
        )
        Holidays.objects.bulk_create([Holidays(**values)])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Holidays.objects.bulk_create([Holidays(**values)])

    def test_same_dates_allowed_in_different_institutions(self):
        a = make_company("University one")
        b = make_company("University two", address="Other")
        values = dict(
            name="Holiday", start_date=date(2030, 1, 1), end_date=date(2030, 1, 1)
        )
        Holidays.objects.bulk_create(
            [Holidays(company_id=a, **values), Holidays(company_id=b, **values)]
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Holidays.objects.bulk_create([Holidays(company_id=a, **values)])

    def test_global_export_permission_is_singleton_at_database_level(self):
        DefaultExportPermission.objects.get_or_create(company_id=None)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DefaultExportPermission.objects.bulk_create(
                [DefaultExportPermission(company_id=None)]
            )

    def test_duplicate_non_null_badge_rejected_without_model_validation(self):
        company = make_company("Badge University")
        a = make_employee(company=company, email="one@badge.test")
        b = make_employee(company=company, email="two@badge.test")
        Employee.objects.entire().filter(pk=a.pk).update(badge_id="STAFF-123")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Employee.objects.entire().filter(pk=b.pk).update(badge_id="STAFF-123")

    def test_multiple_null_badges_remain_allowed(self):
        company = make_company("Null Badge University")
        a = make_employee(company=company, email="null-one@badge.test")
        b = make_employee(company=company, email="null-two@badge.test")
        self.assertIsNone(a.badge_id)
        self.assertIsNone(b.badge_id)

    def test_expected_indexes_exist(self):
        with connection.cursor() as cursor:
            holiday_indexes = connection.introspection.get_constraints(
                cursor, "base_holidays"
            )
            export_indexes = connection.introspection.get_constraints(
                cursor, "base_defaultexportpermission"
            )
        self.assertTrue(holiday_indexes["unique_global_holiday_dates"]["unique"])
        self.assertTrue(
            export_indexes["unique_default_export_permission_all_companies"]["unique"]
        )
