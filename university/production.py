"""Hardened runtime for staging and production; never consumes developer defaults."""

import os
from django.core.exceptions import ImproperlyConfigured
from university.operations.config import prepare_environment, production_errors

prepare_environment(os.environ)
errors = production_errors(os.environ)
if errors:
    raise ImproperlyConfigured(
        "University production configuration rejected:\n- " + "\n- ".join(errors)
    )
os.environ["HORILLA_ENV"] = "production"
from .settings import *  # noqa: E402,F403

HR_DEPLOYMENT_STAGE = os.environ["HR_DEPLOYMENT_STAGE"]
HR_PUBLIC_URL = os.environ["HR_PUBLIC_URL"]
HR_SOURCE_REVISION = os.environ.get("HR_SOURCE_REVISION", "unknown")
INSTALLED_APPS = [*INSTALLED_APPS, "university.operations"]
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 30 * 60
SESSION_SAVE_EVERY_REQUEST = True
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = False
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# Domain-owner submission to the browser preload list is a separate decision.
SECURE_HSTS_PRELOAD = False
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
if os.environ.get("MYSQL_SSL_CA"):
    DATABASES["default"]["OPTIONS"].update(
        ssl={"ca": os.environ["MYSQL_SSL_CA"]}, ssl_mode="VERIFY_IDENTITY"
    )
AXES_IPWARE_PROXY_COUNT = 1
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"]
COMPANY_SCOPED_PERMISSIONS = True
MIDDLEWARE = [
    *MIDDLEWARE,
    "university.operations.middleware.ProductionBoundaryMiddleware",
]
ROOT_URLCONF = "university.operations.urls"
