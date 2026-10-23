from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class HorillaAuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hr_auth"
    # Kept at the original value so migrations, permissions and
    # database tables keep resolving after the package rename.
    label = "horilla_auth"
    verbose_name = _("Authentication")
