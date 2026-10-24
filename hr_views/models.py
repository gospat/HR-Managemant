import json

from django.db import models

from core.horilla_middlewares import _thread_locals
from core.models import HrModel
from hr_auth.models import HorillaUser

# Create your models here.


class ToggleColumn(HrModel):
    """
    ToggleColumn
    """

    user_id = models.ForeignKey(
        HorillaUser,
        on_delete=models.CASCADE,
        related_name="user_excluded_column",
        editable=False,
    )
    path = models.CharField(max_length=256)
    excluded_columns = models.JSONField(default=list)

    def save(self, *args, **kwargs):
        request = getattr(_thread_locals, "request", {})
        user = request.user
        self.user_id = user
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return str(self.user_id.employee_get)


class ActiveTab(HrModel):
    """
    ActiveTab
    """

    path = models.CharField(max_length=256)
    tab_target = models.CharField(max_length=256)


class ActiveGroup(HrModel):
    """
    ActiveGroup
    """

    path = models.CharField(max_length=256)
    group_target = models.CharField(max_length=256)
    group_by_field = models.CharField(max_length=256)


class SavedFilter(HrModel):
    """
    SavedFilter
    """

    title = models.CharField(max_length=20, null=True)
    color = models.CharField(max_length=10, default="")
    is_default = models.BooleanField(default=False)
    filter = models.TextField()
    urlencode = models.TextField(default="")
    path = models.CharField(max_length=256)
    referrer = models.CharField(max_length=256, default="")

    xss_exempt_fields = [
        "urlencode",
    ]

    def save(self, *args, **kwargs):
        SavedFilter.objects.filter(
            is_default=True, path=self.path, created_by=self.created_by
        ).exclude(id=self.pk).update(is_default=False)
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return str(self.title)


class ActiveView(HrModel):
    """
    This model to store the active view type for HNV
    """

    path = models.CharField(max_length=256)
    type = models.CharField(max_length=50)

    def save(self, *args, **kwargs):
        return super().save(*args, **kwargs)


class ColumnOrder(HrModel):
    employee = models.ForeignKey(
        "employee.Employee", on_delete=models.CASCADE, related_name="column_order"
    )
    path = models.CharField(max_length=256)
    column_order = models.JSONField(default=list)

    def save(self, *args, **kwargs):
        request = getattr(_thread_locals, "request", {})
        employee = request.user.employee_get
        self.employee = employee
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return str(self.employee)
