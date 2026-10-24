"""
horilla_automations/filters.py
"""

from core.filters import HrFilterSet, django_filters
from hr_automations.models import MailAutomation


class AutomationFilter(HrFilterSet):
    """
    AutomationFilter
    """

    search = django_filters.CharFilter(field_name="title", lookup_expr="icontains")

    class Meta:
        model = MailAutomation
        fields = "__all__"
