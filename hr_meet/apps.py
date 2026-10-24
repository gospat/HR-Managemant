from django.apps import AppConfig
from django.conf import settings


class HrMeetConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hr_meet"
    # Kept at the original value so migrations, permissions and
    # database tables keep resolving after the package rename.
    label = "horilla_meet"
    verbose_name = "Meet"

    def ready(self):
        from django.urls import include, path

        from core.urls import urlpatterns
        from hr_meet import signals

        settings.APPS.append("horilla_meet")

        urlpatterns.append(
            path("meet/", include("hr_meet.urls")),
        )
        super().ready()
