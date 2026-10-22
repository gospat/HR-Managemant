from django.urls import include, path
from horilla.urls import urlpatterns as upstream_patterns
from university.people.views import (
    SessionView,
    StaffView,
    StaffOptionsView,
    StaffDetailView,
    StaffStatusView,
    StaffHistoryView,
)

urlpatterns = [
    path("university-api/session/", SessionView.as_view()),
    path("university-api/staff/", StaffView.as_view()),
    path("university-api/staff/options/", StaffOptionsView.as_view()),
    path("university-api/staff/<int:pk>/", StaffDetailView.as_view()),
    path("university-api/staff/<int:pk>/status/", StaffStatusView.as_view()),
    path("university-api/staff/<int:pk>/history/", StaffHistoryView.as_view()),
    *upstream_patterns,
]
