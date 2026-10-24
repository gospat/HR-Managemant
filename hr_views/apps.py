from django.apps import AppConfig


class HrViewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hr_views"
    # Kept at the original value so migrations, permissions and
    # database tables keep resolving after the package rename.
    label = "horilla_views"
    # Display-only name; the pinned label above is the database identity.
    verbose_name = "Shared Views"
