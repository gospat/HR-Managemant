"""Explicit ownership checks for registered HR document/profile uploads.

Unregistered module attachments stay denied until their relationships are reviewed.
"""

from pathlib import PurePosixPath


def actor_company_id(user):
    if user.is_superuser:
        return None
    from employee.models import EmployeeWorkInformation

    return (
        EmployeeWorkInformation.objects.entire()
        .filter(employee_id__employee_user_id=user)
        .values_list("company_id_id", flat=True)
        .first()
    )


def is_secret_upload(path):
    from django.apps import apps
    from .rules import NEVER_SERVE

    for label, fields in NEVER_SERVE.items():
        if apps.get_model(label).objects.filter(**{fields[0]: path}).exists():
            return True
    return False


def can_read_media(user, relative_path):
    if (
        not relative_path
        or "\\" in relative_path
        or "%" in relative_path
        or PurePosixPath(relative_path).is_absolute()
        or any(part.startswith(".") for part in relative_path.split("/"))
    ):
        return False
    if relative_path.startswith(("base/icon/", "base/company/icon/")):
        return True
    if not user.is_authenticated:
        return False
    from django.apps import apps
    from django.db.models import Q
    from .rules import RULES

    # Resolve only registered paths. Upload prefixes select candidate models;
    # database field equality establishes the actual resource, never the prefix.
    segments = relative_path.split("/")
    candidate = (segments[0] + "." + segments[1]).lower() if len(segments) > 2 else ""
    if is_secret_upload(relative_path):
        return False
    if not getattr(user, "pk", None):
        return False
    if not user.is_active:
        return False
    if user.is_superuser:
        return True
    scope = actor_company_id(user)
    if not scope:
        return False
    labels = [label for label in RULES if label.lower() == candidate]
    # Legacy document/profile paths predate canonical upload prefixes.
    if not labels:
        labels = ["horilla_documents.Document", "employee.Employee"]
    for label in labels:
        fields, owners, companies = RULES[label]
        model = apps.get_model(label)
        match = Q(pk__in=[])
        for field in fields:
            match |= Q(**{field: relative_path})
        manager = model.objects
        qs = (manager.entire() if hasattr(manager, "entire") else manager.all()).filter(
            match
        )
        # A blob related to another institution must never leak through a second
        # relationship (for example a cross-institution task assignee).
        scope_paths = companies + [
            (owner + "__" if owner else "") + "employee_work_info__company_id"
            for owner in owners
        ]
        for path in scope_paths:
            qs = qs.exclude(~Q(**{path: scope}) & Q(**{path + "__isnull": False}))
        for owner in owners:
            prefix = owner + "__" if owner else ""
            owner_scope = {prefix + "employee_work_info__company_id_id": scope}
            if (
                label not in {"employee.NoteFiles", "employee.DisciplinaryAction"}
                and qs.filter(
                    **owner_scope, **{prefix + "employee_user_id_id": user.pk}
                ).exists()
            ):
                return True
            permission = label.split(".")[0] + ".view_" + model._meta.model_name
            if user.has_perm(permission) and qs.filter(**owner_scope).exists():
                return True
        for company in companies:
            if (
                user.has_perm(model._meta.app_label + ".view_" + model._meta.model_name)
                and qs.filter(**{company: scope}).exists()
            ):
                return True
    return False
