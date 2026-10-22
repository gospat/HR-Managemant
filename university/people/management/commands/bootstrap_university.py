import getpass
import os
import sys
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from base.models import Company, Department
from employee.models import Employee, EmployeeWorkInformation
from horilla_auth.models import HorillaUser


class Command(BaseCommand):
    help = "Create the institution idempotently; optionally provision its first administrator securely."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--admin-email")

    @transaction.atomic
    def handle(self, *args, **options):
        name = options["name"].strip()
        if not name or len(name) > 50:
            raise CommandError("Institution name must be between 1 and 50 characters.")
        email = options.get("admin_email")
        password = None
        if email:
            try:
                validate_email(email)
            except ValidationError as exc:
                raise CommandError(
                    "Enter a valid administrator email address."
                ) from exc
            if (
                HorillaUser.objects.filter(username=email).exists()
                or Employee.objects.entire().filter(email=email).exists()
            ):
                raise CommandError(
                    "This email already exists. No existing account was changed or promoted."
                )
            password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
            if not password:
                if not sys.stdin.isatty():
                    raise CommandError(
                        "Run in an interactive terminal to enter the administrator password, or provide DJANGO_SUPERUSER_PASSWORD securely. Never pass a password as a command argument."
                    )
                password = getpass.getpass("Administrator password: ")
                if password != getpass.getpass("Confirm password: "):
                    raise CommandError("Passwords do not match.")
            candidate = HorillaUser(username=email, email=email)
            try:
                validate_password(password, user=candidate)
            except ValidationError as exc:
                raise CommandError("; ".join(exc.messages)) from exc
        company, _ = Company.objects.get_or_create(
            company=name, defaults={"country": "Nigeria", "hq": True, "address": None}
        )
        department = (
            Department.objects.entire()
            .filter(department="Human Resources", company_id=company)
            .first()
        )
        if department is None:
            department = Department.objects.create(department="Human Resources")
            department.company_id.add(company)
        if email:
            user = HorillaUser.objects.create_superuser(
                username=email, email=email, password=password
            )
            employee = Employee(
                employee_first_name="University",
                employee_last_name="Administrator",
                email=email,
                phone="0000000000",
                employee_user_id=user,
            )
            employee.save()
            EmployeeWorkInformation.objects.update_or_create(
                employee_id=employee,
                defaults={"company_id": company, "department_id": department},
            )
            self.stdout.write(
                "Administrator created. Update the placeholder name and phone after signing in."
            )
        self.stdout.write(
            self.style.SUCCESS(
                "Institution setup complete. Existing records and credentials were preserved."
            )
        )
