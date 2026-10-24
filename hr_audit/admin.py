"""
admin.py
"""

from django.contrib import admin

from hr_audit.models import AuditTag, HorillaAuditInfo, HrAuditLog

# Register your models here.

admin.site.register(AuditTag)
