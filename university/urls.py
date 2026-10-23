from django.urls import include, path
from core.urls import urlpatterns as upstream_patterns
from university.operations.dynamic_routes import dispatch as dynamic_dispatch
from university.people.views import (
    SessionView,
    StaffView,
    StaffOptionsView,
    StaffDetailView,
    StaffStatusView,
    StaffHistoryView,
)

from university.governance.views import (
    PolicyView,
    PolicyAdoptView,
    PromotionView,
    PromotionActionView,
)

urlpatterns = [
    path("university-dynamic/<slug:token>/", dynamic_dispatch),
    path("university-api/policies/", PolicyView.as_view()),
    path("university-api/policies/<int:pk>/adopt/", PolicyAdoptView.as_view()),
    path("university-api/promotions/", PromotionView.as_view()),
    path("university-api/promotions/<int:pk>/action/", PromotionActionView.as_view()),
    path("university-api/session/", SessionView.as_view()),
    path("university-api/staff/", StaffView.as_view()),
    path("university-api/staff/options/", StaffOptionsView.as_view()),
    path("university-api/staff/<int:pk>/", StaffDetailView.as_view()),
    path("university-api/staff/<int:pk>/status/", StaffStatusView.as_view()),
    path("university-api/staff/<int:pk>/history/", StaffHistoryView.as_view()),
    *upstream_patterns,
]
