"""Standalone Nigerian university configuration on top of Horilla."""

from horilla.settings import *  # noqa: F403

TIME_ZONE = "Africa/Lagos"
USE_TZ = True
if DATABASES["default"]["ENGINE"] != "django.db.backends.mysql":  # noqa: F405
    raise RuntimeError("University HR requires a MySQL DATABASE_URL.")
DATABASES["default"].setdefault("OPTIONS", {}).update(  # noqa: F405
    charset="utf8mb4", init_command="SET sql_mode='STRICT_TRANS_TABLES'"
)

INSTALLED_APPS = [*INSTALLED_APPS, "university.people.apps.PeopleConfig", "university.governance"]
ROOT_URLCONF = "university.urls"
