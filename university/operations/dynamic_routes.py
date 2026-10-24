"""Shared, session-bound dispatch for legacy modal/import/bulk callbacks.

Store only server-created view definitions, never request objects or callables.
The public opaque token is not a session credential; every dispatch rechecks
its session, actor, institution and current permissions.
"""

import json
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.module_loading import import_string
from django.views import View
from django.views.decorators.cache import never_cache
from university.documents.access import actor_company_id

PREFIX = "university:dynamic:"
METHOD_PERMISSIONS = {
    "serve_bulk_form": "change",
    "handle_bulk_submission": "change",
    "serve_import_sheet": "add",
    "import_records": "add",
}


def session_digest(request):
    return salted_hmac(
        "university.dynamic.session",
        request.session.session_key or "",
        algorithm="sha256",
    ).hexdigest()


def register(route, view):
    from core.hr_middlewares import _thread_locals

    request = getattr(_thread_locals, "request", None)
    if (
        not request
        or not request.user.is_authenticated
        or not request.user.is_active
        or not request.session.session_key
    ):
        raise PermissionDenied("Sign in before opening this form.")
    company_id = actor_company_id(request.user)
    if not request.user.is_superuser and not company_id:
        raise PermissionDenied("An institution assignment is required.")
    owner = getattr(view, "__self__", None)
    if owner is None:
        cls = getattr(view, "view_class", None)
        definition = {
            "method": None,
            "init_kwargs": getattr(view, "view_initkwargs", {}),
        }
    else:
        cls = type(owner)
        if view.__name__ not in METHOD_PERMISSIONS:
            raise ValueError("Unsupported dynamic callback.")
        definition = {
            "method": view.__name__,
            "init_kwargs": {},
            "kwargs": getattr(owner, "kwargs", {}),
            "state": {
                name: getattr(owner, name)
                for name in ("view_id", "post_bulk_path")
                if hasattr(owner, name)
            },
        }
    if cls is None or not issubclass(cls, View):
        raise ValueError("Dynamic routes require an importable Django view.")
    definition.update(
        view_class=cls.__module__ + "." + cls.__qualname__,
        actor_id=request.user.pk,
        session_digest=session_digest(request),
        company_id=company_id,
    )
    # Round trip rejects unserializable request/queryset/callable state early.
    definition = json.loads(json.dumps(definition))
    token = salted_hmac(
        "university.dynamic.route",
        route + "|" + definition["view_class"] + "|" + str(request.user.pk),
        algorithm="sha256",
    ).hexdigest()
    if definition["method"] == "handle_bulk_submission":
        definition["state"]["post_bulk_path"] = "university-dynamic/" + token + "/"
    cache.set(
        PREFIX + token, definition, timeout=min(1800, settings.SESSION_COOKIE_AGE)
    )
    return "university-dynamic/" + token + "/"


@never_cache
def dispatch(request, token):
    if not request.user.is_authenticated or not request.user.is_active:
        raise PermissionDenied("Sign in before opening this form.")
    company_id = actor_company_id(request.user)
    if not request.user.is_superuser and not company_id:
        raise PermissionDenied("An institution assignment is required.")
    definition = cache.get(PREFIX + token)
    if (
        not definition
        or definition["actor_id"] != request.user.pk
        or not constant_time_compare(
            definition["session_digest"], session_digest(request)
        )
        or definition["company_id"] != company_id
    ):
        raise Http404("This form expired. Reopen it from its module.")
    cls = import_string(definition["view_class"])
    if not issubclass(cls, View):
        raise Http404()
    method = definition["method"]
    if method is None:
        model = cls.model
        if not request.user.has_perm(
            f"{model._meta.app_label}.add_{model._meta.model_name}"
        ):
            raise PermissionDenied("The required module permission is missing.")
        return cls.as_view(**definition["init_kwargs"])(request)
    if method not in METHOD_PERMISSIONS:
        raise Http404()
    model = cls.model
    permission = (
        f"{model._meta.app_label}.{METHOD_PERMISSIONS[method]}_{model._meta.model_name}"
    )
    if not request.user.has_perm(permission):
        raise PermissionDenied("The required module permission is missing.")
    instance = cls(**definition["init_kwargs"])
    instance.setup(request, **definition.get("kwargs", {}))
    for name, value in definition.get("state", {}).items():
        setattr(instance, name, value)
    return getattr(instance, method)(request)
