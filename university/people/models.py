from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from base.horilla_company_manager import HorillaCompanyManager


class Faculty(models.Model):
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT)
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20)
    objects = HorillaCompanyManager(related_company_field="company")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="unique_university_faculty_code"
            )
        ]
        verbose_name_plural = "Faculties / directorates"

    def __str__(self):
        return self.name


class StaffProfile(models.Model):
    class Category(models.TextChoices):
        TEACHING = "teaching", "Teaching"
        NON_TEACHING = "non_teaching", "Non-teaching"

    employee = models.OneToOneField(
        "employee.Employee", on_delete=models.CASCADE, related_name="university_profile"
    )
    category = models.CharField(max_length=20, choices=Category.choices)
    faculty = models.ForeignKey(
        Faculty, on_delete=models.PROTECT, null=True, blank=True
    )
    rank = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [
            ("change_staff_status", "Can archive and restore university staff records"),
            ("restore_staff_login", "Can restore staff login access"),
            ("view_staff_history", "Can view university staff change history"),
        ]

    def clean(self):
        if self.faculty_id and self.employee_id:
            from employee.models import EmployeeWorkInformation

            company_id = (
                EmployeeWorkInformation.objects.filter(employee_id=self.employee_id)
                .values_list("company_id_id", flat=True)
                .first()
            )
            if company_id != self.faculty.company_id:
                raise ValidationError(
                    {
                        "faculty": "Faculty must belong to the staff member’s institution."
                    }
                )

    def __str__(self):
        return f"{self.employee} — {self.get_category_display()}"


class StaffChange(models.Model):
    """Append-only application audit records; no salary or password data."""

    employee = models.ForeignKey("employee.Employee", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=30)
    reason = models.CharField(max_length=500, blank=True, default="")
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
