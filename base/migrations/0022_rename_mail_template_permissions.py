"""Rewrite the HorillaMailTemplate permission display names.

Django's ``create_permissions`` post-migrate hook only *creates* missing
permissions -- it never refreshes the ``name`` of an existing one. So giving
``HorillaMailTemplate`` an explicit ``Meta.verbose_name`` (migration 0021) fixed
the content-type name but left ``auth_permission.name`` still reading
"Can add horilla mail template". This rewrites the human-readable names while
leaving ``codename`` (the identity used by every permission check) untouched.

On a fresh database this migration is a no-op: the permissions do not exist yet
when it runs, and the post-migrate hook then creates them with the already
correct names.
"""

from django.db import migrations

OLD_VERBOSE_NAME = "horilla mail template"
NEW_VERBOSE_NAME = "Mail Template"
ACTIONS = ("add", "change", "delete", "view", "export")


def _rename(apps, verbose_name):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    for ct in ContentType.objects.filter(
        app_label="base", model="horillamailtemplate"
    ):
        for action in ACTIONS:
            Permission.objects.filter(
                content_type=ct,
                codename=f"{action}_horillamailtemplate",
            ).update(name=f"Can {action} {verbose_name}")


def forwards(apps, schema_editor):
    _rename(apps, NEW_VERBOSE_NAME)


def backwards(apps, schema_editor):
    _rename(apps, OLD_VERBOSE_NAME)


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0021_alter_horillamailtemplate_options_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
