from django.apps import AppConfig


class PeopleConfig(AppConfig):
    name = "university.people"
    label = "university_people"
    verbose_name = "University staff"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from django.db.models.signals import post_migrate
        from .signals import ensure_global_export_default

        post_migrate.connect(
            ensure_global_export_default,
            sender=self,
            dispatch_uid="university.ensure_global_export_default",
        )
