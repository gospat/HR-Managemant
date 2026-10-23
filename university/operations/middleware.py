from django.http import HttpResponseNotFound, HttpResponseForbidden


class ProductionBoundaryMiddleware:
    """Close first-run setup and unreviewed media access in the hardened runtime."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if path.startswith(("/initialize-database", "/load-demo", "/load-data")):
            return HttpResponseNotFound()
        if path.startswith("/media/"):
            from university.documents.access import can_read_media

            if not can_read_media(request.user, path[len("/media/") :]):
                response = HttpResponseForbidden(
                    "You do not have access to this document."
                )
                response["Cache-Control"] = "private, no-store"
                return response
        response = self.get_response(request)
        if path.startswith(
            (
                "/university-api/",
                "/university-dynamic/",
                "/admin/",
                "/login",
                "/change-password",
                "/media/",
            )
        ):
            response["Cache-Control"] = "private, no-store"
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
