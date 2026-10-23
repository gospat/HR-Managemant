"""Rebrand the seeded onboarding-tour copy in existing databases.

The tour seed migrations shipped vendor branding in their wording. This
deployment is white-labelled, so any tour or step text that already contains
the vendor name is rewritten to the institution's own name. The update is
idempotent: it only touches rows that still contain the vendor name.
"""

from django.db import migrations

VENDOR_NAME = "Horilla"
BRAND_NAME = "Bells University of Technology"


def rebrand(apps, schema_editor):
    Tour = apps.get_model("horilla_tour", "Tour")
    TourStep = apps.get_model("horilla_tour", "TourStep")

    for model, fields in (
        (Tour, ("title", "description")),
        (TourStep, ("title", "description")),
    ):
        for field in fields:
            for record in model.objects.filter(**{f"{field}__contains": VENDOR_NAME}):
                value = getattr(record, field)
                setattr(record, field, value.replace(VENDOR_NAME, BRAND_NAME))
                record.save(update_fields=[field])


class Migration(migrations.Migration):

    dependencies = [
        ("horilla_tour", "0088_alter_tour_is_active_alter_tourprogress_is_active_and_more"),
    ]

    operations = [
        migrations.RunPython(rebrand, migrations.RunPython.noop),
    ]
