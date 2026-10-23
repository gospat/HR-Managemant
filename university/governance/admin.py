from django.contrib import admin, messages
from django.core.exceptions import ValidationError, PermissionDenied
from university.people.admin import SuperuserOnlyAdmin
from .models import UniversityPolicy, PromotionRequest, PromotionEvent
from .services import adopt_policy


@admin.register(UniversityPolicy)
class PolicyAdmin(SuperuserOnlyAdmin):
    list_display = [
        "company",
        "module",
        "version",
        "provisional",
        "active",
        "adopted_by",
        "adopted_at",
    ]
    list_filter = ["company", "module", "active"]
    readonly_fields = ["active", "adopted_by", "adopted_at", "created_at"]
    actions = ["adopt_selected"]

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.adopted_at:
            return [field.name for field in self.model._meta.fields]
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(
        description="Adopt reviewed templates (provisional status is retained)"
    )
    def adopt_selected(self, request, queryset):
        for policy in queryset:
            try:
                adopt_policy(request.user, policy.pk)
            except (ValidationError, PermissionDenied) as exc:
                self.message_user(request, str(exc), level=messages.ERROR)


class AuditOnlyAdmin(SuperuserOnlyAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PromotionRequest)
class PromotionAdmin(AuditOnlyAdmin):
    list_display = [
        "employee",
        "source_rank",
        "proposed_rank",
        "effective_date",
        "status",
        "revision",
    ]
    list_filter = ["status", "policy__company"]


@admin.register(PromotionEvent)
class PromotionEventAdmin(AuditOnlyAdmin):
    list_display = ["promotion", "actor", "action", "created_at"]
