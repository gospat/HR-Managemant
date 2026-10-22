from django.http import HttpResponseNotFound, HttpResponseForbidden


class ProductionBoundaryMiddleware:
    """Close first-run setup and unreviewed media access in the hardened runtime."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if path.startswith(("/initialize-database", "/load-demo", "/load-data")):
            return HttpResponseNotFound()
        if path.startswith("/media/") and not path.startswith(
            ("/media/base/icon/", "/media/base/company/icon/")
        ):
            # Upstream checks authentication but does not establish file ownership
            # for every HR module. Fail closed until those ACLs are accepted.
            if not request.user.is_authenticated or not request.user.is_superuser:
                return HttpResponseForbidden(
                    "Document access requires an approved file access policy."
                )
        response = self.get_response(request)
        if path.startswith(
            ("/university-api/", "/admin/", "/login", "/change-password", "/media/")
        ):
            response["Cache-Control"] = "private, no-store"
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
