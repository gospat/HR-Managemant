"""Standalone Nigerian university configuration on top of Horilla."""

import os

from core.settings import *  # noqa: F403

TIME_ZONE = "Africa/Lagos"
USE_TZ = True

# White-label branding. With WHITE_LABELLING on, the product name and logo shown
# to users come from the institution record (base.Company) rather than the
# upstream vendor defaults. BRAND_FALLBACK_NAME is used only when no institution
# record can be resolved, so a vendor name can never leak into the interface.
WHITE_LABELLING = True
BRAND_FALLBACK_NAME = os.environ.get(
    "BRAND_FALLBACK_NAME", "Bells University of Technology"
)
# In-app help buttons used to send users to the vendor's documentation site.
# Point them at the institution's own documentation so no third-party link is
# published to staff.
DOC_BASE_URL = os.environ.get("DOC_BASE_URL", "https://hr.bells.edu.ng")

if DATABASES["default"]["ENGINE"] != "django.db.backends.mysql":  # noqa: F405
    raise RuntimeError("University HR requires a MySQL DATABASE_URL.")
DATABASES["default"].setdefault("OPTIONS", {}).update(  # noqa: F405
    charset="utf8mb4", init_command="SET sql_mode='STRICT_TRANS_TABLES'"
)

INSTALLED_APPS = [*INSTALLED_APPS, "university.people.apps.PeopleConfig", "university.governance"]
ROOT_URLCONF = "university.urls"
