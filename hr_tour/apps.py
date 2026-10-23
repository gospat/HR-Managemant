from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class HorillaTourConfig(AppConfig):
    """
    App config for the enterprise product-tour engine.

    Global tours (``company_id=None``) are visible to every tenant because
    ``HorillaCompanyManager`` includes ``company_id__isnull=True`` rows, so no
    per-company seeding/signals are required.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "hr_tour"
    # Kept at the original value so migrations, permissions and
    # database tables keep resolving after the package rename.
    label = "horilla_tour"
    verbose_name = _("Product Tours")

    def ready(self):
        # Register the "Product Tours" entry in the Settings sidebar menu.
        from hr_tour import sidebar  # noqa: F401

        return super().ready()
