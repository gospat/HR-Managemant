from django.apps import AppConfig


class HorillaCrumbsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hr_crumbs"
    # Keep the original app label so existing migrations, permissions and
    # database tables keep resolving after the package rename.
    label = "horilla_crumbs"
    # Display-only name; the pinned label above is the database identity.
    verbose_name = "Breadcrumbs"
