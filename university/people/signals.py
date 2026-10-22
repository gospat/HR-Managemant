"""Defaults that must survive a fresh database or a development/test flush."""


def ensure_global_export_default(sender, using="default", **kwargs):
    from base.models import DefaultExportPermission

    # get_or_create deliberately preserves an administrator's existing choice.
    DefaultExportPermission.objects.using(using).get_or_create(
        company_id=None, defaults={"is_enabled": True}
    )
