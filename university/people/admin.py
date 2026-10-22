from django.contrib import admin
from .models import Faculty, StaffProfile, StaffChange


class SuperuserOnlyAdmin(admin.ModelAdmin):
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Faculty)
class FacultyAdmin(SuperuserOnlyAdmin):
    list_display = ["name", "code", "company"]
    search_fields = ["name", "code"]


@admin.register(StaffProfile)
class StaffProfileAdmin(SuperuserOnlyAdmin):
    list_display = ["employee", "category", "faculty", "rank"]
    list_filter = ["category", "faculty"]
    search_fields = [
        "employee__employee_first_name",
        "employee__email",
        "employee__badge_id",
    ]
    autocomplete_fields = []


@admin.register(StaffChange)
class StaffChangeAdmin(SuperuserOnlyAdmin):
    list_display = ["employee", "actor", "action", "created_at"]
    readonly_fields = ["employee", "actor", "action", "reason", "changes", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
