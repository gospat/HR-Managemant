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
    if user.is_superuser:
        return True
    if not getattr(user, "pk", None) or not user.is_active:
        return False
    from employee.models import Employee
    from horilla_documents.models import Document

    scope = actor_company_id(user)
    if not scope:
        return False
    # Ownership is established from database relations, never filenames,
    # guessed employee IDs or a client-selected company/session value.
    documents = Document.objects.entire().filter(
        document=relative_path,
        employee_id__employee_work_info__company_id_id=scope,
        employee_id__is_active=True,
    )
    if documents.filter(employee_id__employee_user_id=user).exists():
        return True
    if user.has_perm("horilla_documents.view_document") and documents.exists():
        return True
    return (
        Employee.objects.entire()
        .filter(
            employee_profile=relative_path,
            employee_user_id=user,
            is_active=True,
            employee_work_info__company_id_id=scope,
        )
        .exists()
    )
