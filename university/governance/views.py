from django.core.exceptions import (
    ValidationError,
    PermissionDenied as DjangoPermissionDenied,
)
from django.http import Http404
from django.core.exceptions import ObjectDoesNotExist
from collections.abc import Mapping
from django.utils.dateparse import parse_date
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from university.documents.access import actor_company_id
from .models import UniversityPolicy, PromotionRequest
from .services import request_promotion, transition_promotion, adopt_policy


def case_json(case):
    return {
        "id": case.pk,
        "employee_id": case.employee_id,
        "employee": str(case.employee),
        "source_rank": case.source_rank,
        "proposed_rank": case.proposed_rank,
        "status": case.status,
        "effective_date": case.effective_date.isoformat(),
        "revision": case.revision,
        "policy_version": case.policy.version,
        "provisional_policy": case.policy.provisional,
        "requested_by": case.requested_by_id,
        "reviewed_by": case.reviewed_by_id,
        "approved_by": case.approved_by_id,
        "evidence": case.evidence,
        "events": [
            {
                "action": event.action,
                "reason": event.reason,
                "actor_id": event.actor_id,
                "created_at": event.created_at,
            }
            for event in case.events.all()
        ],
    }


class GovernanceView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        if isinstance(exc, ValidationError):
            return Response({"detail": " ".join(exc.messages)}, status=400)
        if isinstance(exc, ObjectDoesNotExist):
            return super().handle_exception(Http404())
        return super().handle_exception(exc)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response


class PolicyView(GovernanceView):
    def get(self, request):
        if not request.user.has_perm("university_governance.view_universitypolicy"):
            raise DjangoPermissionDenied()
        policies = UniversityPolicy.objects.select_related("company").order_by(
            "module", "-created_at"
        )
        if not request.user.is_superuser:
            scope = actor_company_id(request.user)
            policies = policies.filter(company_id=scope) if scope else policies.none()
        return Response(
            {
                "results": list(
                    policies.values(
                        "id",
                        "company_id",
                        "module",
                        "version",
                        "configuration",
                        "provisional",
                        "active",
                        "adopted_at",
                    )
                ),
                "can_adopt": request.user.has_perm(
                    "university_governance.adopt_university_policy"
                ),
            }
        )


class PolicyAdoptView(GovernanceView):
    def post(self, request, pk):
        policy = adopt_policy(request.user, pk)
        return Response(
            {
                "id": policy.pk,
                "active": policy.active,
                "provisional": policy.provisional,
            }
        )


class PromotionView(GovernanceView):
    def get(self, request):
        if not request.user.has_perm("university_governance.view_promotionrequest"):
            raise DjangoPermissionDenied()
        qs = PromotionRequest.objects.select_related(
            "employee", "policy"
        ).prefetch_related("events")
        if not request.user.is_superuser:
            scope = actor_company_id(request.user)
            qs = (
                qs.filter(employee__employee_work_info__company_id_id=scope)
                if scope
                else qs.none()
            )
        from rest_framework.pagination import PageNumberPagination

        pager = PageNumberPagination()
        pager.page_size = 25
        page = pager.paginate_queryset(qs, request)
        result = pager.get_paginated_response([case_json(row) for row in page])
        result.data["permissions"] = {
            name: request.user.has_perm("university_governance." + name)
            for name in [
                "add_promotionrequest",
                "review_promotion",
                "approve_promotion",
                "apply_promotion",
            ]
        }
        return result

    def post(self, request):
        allowed = {
            "employee_id",
            "policy_id",
            "proposed_rank",
            "effective_date",
            "evidence",
        }
        if not isinstance(request.data, Mapping) or set(request.data) != allowed:
            raise ValidationError(
                "Supply only employee, policy, proposed rank, effective date and evidence."
            )
        try:
            date = parse_date(request.data["effective_date"])
            employee_id = int(request.data["employee_id"])
            policy_id = int(request.data["policy_id"])
        except (ValueError, TypeError):
            raise ValidationError("Provide valid staff/policy IDs and an ISO date.")
        if (
            not date
            or not isinstance(request.data["proposed_rank"], str)
            or not isinstance(request.data["evidence"], str)
        ):
            raise ValidationError("Provide a date, rank and promotion evidence.")
        case = request_promotion(
            request.user,
            employee_id,
            policy_id,
            request.data["proposed_rank"],
            date,
            request.data["evidence"],
        )
        return Response(case_json(case), status=201)


class PromotionActionView(GovernanceView):
    def post(self, request, pk):
        if (
            not isinstance(request.data, Mapping)
            or set(request.data) != {"action", "revision", "reason"}
            or not isinstance(request.data.get("action"), str)
            or not isinstance(request.data.get("reason"), str)
            or type(request.data.get("revision")) is not int
        ):
            raise ValidationError(
                "Supply an action, integer revision and audit reason."
            )
        case = transition_promotion(
            request.user,
            pk,
            request.data["action"],
            request.data["revision"],
            request.data["reason"],
        )
        return Response(case_json(case))
