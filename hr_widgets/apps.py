from django.apps import AppConfig


class HorillaWidgetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hr_widgets"
    # Kept at the original value so migrations, permissions and
    # database tables keep resolving after the package rename.
    label = "horilla_widgets"
    # Display-only name; the pinned label above is the database identity.
    verbose_name = "UI Widgets"

    def ready(self):
        from hr_widgets.widgets.file_widgets import patch_clearable_file_input

        patch_clearable_file_input()
