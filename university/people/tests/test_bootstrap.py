from io import StringIO
from unittest.mock import patch
from django.core.management import call_command, CommandError
from django.test import TestCase
from base.models import Company, Department
from employee.models import Employee
from hr_auth.models import HorillaUser


class BootstrapTests(TestCase):
    def test_institution_setup_is_repeatable(self):
        for _ in range(2):
            call_command(
                "bootstrap_university", name="Test University", stdout=StringIO()
            )
        self.assertEqual(Company.objects.filter(company="Test University").count(), 1)
        self.assertEqual(
            Department.objects.entire().filter(department="Human Resources").count(), 1
        )

    @patch.dict(
        "os.environ", {"DJANGO_SUPERUSER_PASSWORD": "Test-only-Strong-Secret-93284"}
    )
    def test_administrator_has_employee_record_and_valid_password(self):
        output = StringIO()
        call_command(
            "bootstrap_university",
            name="Test University",
            admin_email="admin@example.test",
            stdout=output,
        )
        user = HorillaUser.objects.get(username="admin@example.test")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("Test-only-Strong-Secret-93284"))
        self.assertEqual(
            Employee.objects.entire()
            .get(employee_user_id=user)
            .employee_work_info.company_id.company,
            "Test University",
        )
        self.assertNotIn("Test-only-Strong-Secret-93284", output.getvalue())

    @patch.dict(
        "os.environ", {"DJANGO_SUPERUSER_PASSWORD": "Test-only-Strong-Secret-93284"}
    )
    def test_existing_user_is_never_promoted_or_overwritten(self):
        user = HorillaUser.objects.create_user(
            username="staff@example.test", email="staff@example.test", password=None
        )
        with self.assertRaises(CommandError):
            call_command(
                "bootstrap_university",
                name="Test University",
                admin_email="staff@example.test",
                stdout=StringIO(),
            )
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.has_usable_password())

    @patch.dict("os.environ", {"DJANGO_SUPERUSER_PASSWORD": "password"})
    def test_weak_password_does_not_leave_partial_setup(self):
        with self.assertRaises(CommandError):
            call_command(
                "bootstrap_university",
                name="Rejected University",
                admin_email="admin@example.test",
                stdout=StringIO(),
            )
        self.assertFalse(Company.objects.filter(company="Rejected University").exists())

    def test_post_migrate_default_preserves_administrator_choice(self):
        from base.models import DefaultExportPermission
        from university.people.signals import ensure_global_export_default

        setting, _ = DefaultExportPermission.objects.get_or_create(company_id=None)
        setting.is_enabled = False
        setting.save()
        ensure_global_export_default(sender=None)
        setting.refresh_from_db()
        self.assertFalse(setting.is_enabled)
        self.assertEqual(
            DefaultExportPermission.objects.filter(company_id=None).count(), 1
        )
