from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class HorillaDoumentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hr_documents"
    # Kept at the original value so migrations, permissions and
    # database tables keep resolving after the package rename.
    label = "horilla_documents"
    verbose_name = _("Documents")
