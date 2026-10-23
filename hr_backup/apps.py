from django.apps import AppConfig


class BackupConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hr_backup"
    # Kept at the original value so migrations, permissions and
    # database tables keep resolving after the package rename.
    label = "horilla_backup"
    # Display-only name; the pinned label above is the database identity.
    verbose_name = "Backups"

    def ready(self):
        from django.urls import include, path

        from core.urls import urlpatterns

        urlpatterns.append(
            path("backup/", include("hr_backup.urls")),
        )
        super().ready()
