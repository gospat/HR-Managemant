from django.shortcuts import get_object_or_404
from django.contrib.auth import logout
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.middleware.csrf import get_token
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from base.models import Company, Department
from .models import Faculty, StaffChange
from .serializers import (
    StaffCreateSerializer,
    StaffUpdateSerializer,
    StaffStatusSerializer,
)
from .services import (
    company_scope,
    scoped_employees,
    create_staff,
    staff_record,
    staff_detail,
    update_staff,
    change_staff_status,
    StaleStaffRecord,
)


class PrivateAPIView(APIView):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response


class SessionView(PrivateAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        user = request.user
        return Response(
            {
                "authenticated": user.is_authenticated,
                "csrf": get_token(request),
                "can_view_staff": (
                    user.has_perm("employee.view_employee")
                    if user.is_authenticated
                    else False
                ),
                "can_edit_staff": (
                    user.has_perm("employee.change_employee")
                    if user.is_authenticated
                    else False
                ),
                "can_change_status": (
                    user.has_perm("university_people.change_staff_status")
                    if user.is_authenticated
                    else False
                ),
                "can_restore_login": (
                    user.has_perm("university_people.restore_staff_login")
                    if user.is_authenticated
                    else False
                ),
                "can_view_history": (
                    user.has_perm("university_people.view_staff_history")
                    if user.is_authenticated
                    else False
                ),
                "can_add_staff": (
                    user.has_perm("employee.add_employee")
                    if user.is_authenticated
                    else False
                ),
            }
        )

    def delete(self, request):
        # SessionAuthentication enforces CSRF before an authenticated logout.
        logout(request._request)
        return Response(status=204)


class StaffView(PrivateAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.has_perm("employee.view_employee"):
            raise PermissionDenied("HR staff directory access is required.")
        qs = scoped_employees(request.user).order_by(
            "employee_last_name", "employee_first_name", "pk"
        )
        query = request.query_params.get("q", "")[:100].strip()
        if query:
            qs = qs.filter(
                Q(employee_first_name__icontains=query)
                | Q(employee_last_name__icontains=query)
                | Q(email__icontains=query)
                | Q(badge_id__icontains=query)
            )
        category = request.query_params.get("category", "")
        if category:
            if category not in ["teaching", "non_teaching"]:
                return Response({"detail": "Invalid staff category."}, status=400)
            qs = qs.filter(university_profile__category=category)
        pager = PageNumberPagination()
        pager.page_size = 25
        page = pager.paginate_queryset(qs, request)
        return pager.get_paginated_response([staff_record(row) for row in page])

    def post(self, request):
        if not request.user.has_perm("employee.add_employee"):
            raise PermissionDenied("HR staff creation access is required.")
        serializer = StaffCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            employee = create_staff(actor=request.user, data=serializer.validated_data)
        except Company.DoesNotExist:
            return Response({"company_id": ["Institution does not exist."]}, status=400)
        except ValidationError as exc:
            return Response(
                (
                    exc.message_dict
                    if hasattr(exc, "message_dict")
                    else {"detail": exc.messages}
                ),
                status=400,
            )
        except IntegrityError:
            return Response(
                {"detail": "A record with these unique details already exists."},
                status=409,
            )
        return Response(staff_record(employee), status=201)


class StaffOptionsView(PrivateAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (
            request.user.has_perm("employee.add_employee")
            or request.user.has_perm("employee.change_employee")
        ):
            raise PermissionDenied("HR staff editing or creation access is required.")
        companies = Company.objects.all()
        if not request.user.is_superuser:
            companies = companies.filter(pk=company_scope(request.user))
        ids = list(companies.values_list("id", flat=True))
        return Response(
            {
                "companies": list(companies.values("id", "company")),
                "departments": [
                    {
                        "id": d.pk,
                        "department": d.department,
                        "company_ids": list(d.company_id.values_list("id", flat=True)),
                    }
                    for d in Department.objects.entire()
                    .filter(company_id__in=ids)
                    .distinct()
                    .prefetch_related("company_id")
                ],
                "faculties": list(
                    Faculty.objects.filter(company_id__in=ids).values(
                        "id", "name", "company_id"
                    )
                ),
            }
        )


class StaffDetailView(PrivateAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not request.user.has_perm("employee.view_employee"):
            raise PermissionDenied("HR staff directory access is required.")
        employee = get_object_or_404(scoped_employees(request.user), pk=pk)
        return Response(staff_detail(employee, actor=request.user))

    def patch(self, request, pk):
        if not request.user.has_perm(
            "employee.view_employee"
        ) or not request.user.has_perm("employee.change_employee"):
            raise PermissionDenied("HR staff editing access is required.")
        get_object_or_404(scoped_employees(request.user), pk=pk)
        serializer = StaffUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return mutation_response(
            update_staff, request.user, pk, serializer.validated_data
        )


class StaffStatusView(PrivateAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.has_perm(
            "employee.view_employee"
        ) or not request.user.has_perm("university_people.change_staff_status"):
            raise PermissionDenied("HR staff status permission is required.")
        get_object_or_404(scoped_employees(request.user), pk=pk)
        serializer = StaffStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return mutation_response(
            change_staff_status, request.user, pk, serializer.validated_data
        )


class StaffHistoryView(PrivateAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not request.user.has_perm(
            "employee.view_employee"
        ) or not request.user.has_perm("university_people.view_staff_history"):
            raise PermissionDenied("HR change-history permission is required.")
        employee = get_object_or_404(scoped_employees(request.user), pk=pk)
        pager = PageNumberPagination()
        pager.page_size = 25
        events = (
            StaffChange.objects.filter(employee=employee)
            .select_related("actor")
            .order_by("-pk")
        )
        page = pager.paginate_queryset(events, request)
        return pager.get_paginated_response(
            [
                {
                    "id": event.pk,
                    "action": event.action,
                    "actor": event.actor.get_full_name() or event.actor.username,
                    "reason": event.reason,
                    "changes": event.changes,
                    "created_at": event.created_at.isoformat(),
                }
                for event in page
            ]
        )


def mutation_response(service, actor, pk, data):
    try:
        employee = service(actor=actor, employee_id=pk, data=data)
    except StaleStaffRecord:
        return Response(
            {
                "code": "stale_record",
                "detail": "This record changed after you opened it. Reload the latest record before saving.",
            },
            status=409,
        )
    except ValidationError as exc:
        return Response(
            (
                exc.message_dict
                if hasattr(exc, "message_dict")
                else {"detail": exc.messages}
            ),
            status=400,
        )
    except IntegrityError:
        return Response(
            {"detail": "A record with these unique details already exists."}, status=409
        )
    return Response(staff_detail(employee, actor=actor))
