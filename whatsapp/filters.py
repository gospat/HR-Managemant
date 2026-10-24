import django_filters

from core.filters import HrFilterSet
from whatsapp.models import WhatsappCredientials


class CredentialsViewFilter(HrFilterSet):
    search = django_filters.CharFilter(
        field_name="meta_phone_number", lookup_expr="icontains"
    )

    class Meta:
        model = WhatsappCredientials
        fields = ["meta_phone_number", "search"]
