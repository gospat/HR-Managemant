"""Horilla ``AppLauncher`` for the database-backed template app."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class HorillaDBTemplateConfig(AppConfig):
    """Horilla app config: registers ``horilla_dbtemplate`` and auto-imports signal handlers."""

    default = True

    name = "hr_dbtemplate"
    # Kept at the original value so migrations, permissions and
    # database tables keep resolving after the package rename.
    label = "horilla_dbtemplate"
    verbose_name = _("Database Templates")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals

        return super().ready()
