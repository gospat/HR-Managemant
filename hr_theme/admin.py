"""
Admin registration for the appearance app.
"""

from django.conf import settings
from django.contrib import admin

from hr_theme.models import CompanyTheme, HorillaColorTheme

# Django admin branding. The built-in admin is not part of the white-labelled
# interface and never reads the institution record, so without this it would
# present itself to university staff as "Django administration".
_brand = getattr(settings, "BRAND_FALLBACK_NAME", "Bells University of Technology")
admin.site.site_header = _brand
admin.site.site_title = _brand
admin.site.index_title = "Administration"

# Register your models here.
admin.site.register(HorillaColorTheme)
admin.site.register(CompanyTheme)
