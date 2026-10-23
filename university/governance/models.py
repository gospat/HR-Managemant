from django.conf import settings
from django.db import models
from base.horilla_company_manager import HorillaCompanyManager


class UniversityPolicy(models.Model):
    objects = HorillaCompanyManager(related_company_field="company")
    company = models.ForeignKey("base.Company", on_delete=models.PROTECT)
    module = models.CharField(max_length=30)
    version = models.CharField(max_length=60)
    configuration = models.JSONField(default=dict)
    provisional = models.BooleanField(default=True)
    active = models.BooleanField(default=False)
    adopted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )
    adopted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "module", "version"],
                name="unique_university_policy_version",
            )
        ]
        permissions = [
            (
                "adopt_university_policy",
                "Can adopt an explicitly reviewed university policy template",
            )
        ]

    def __str__(self):
        return f"{self.company} / {self.module} / {self.version}"


class PromotionRequest(models.Model):
    employee = models.ForeignKey("employee.Employee", on_delete=models.PROTECT)
    policy = models.ForeignKey(UniversityPolicy, on_delete=models.PROTECT)
    policy_snapshot = models.JSONField(default=dict)
    source_rank = models.CharField(max_length=100)
    proposed_rank = models.CharField(max_length=100)
    effective_date = models.DateField()
    evidence = models.TextField(max_length=4000)
    status = models.CharField(
        max_length=20,
        default="submitted",
        choices=[
            (s, s.title())
            for s in ("submitted", "recommended", "approved", "rejected", "applied")
        ],
    )
    revision = models.PositiveIntegerField(default=1)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="promotion_requests",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotion_reviews",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotion_approvals",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [
            ("review_promotion", "Can recommend university promotions"),
            ("approve_promotion", "Can approve university promotions as Registrar"),
            ("apply_promotion", "Can apply an approved university promotion"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee}: {self.source_rank} → {self.proposed_rank} ({self.status})"


class PromotionEvent(models.Model):
    promotion = models.ForeignKey(
        PromotionRequest, on_delete=models.PROTECT, related_name="events"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=30)
    reason = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
