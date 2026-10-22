from django.urls import path
from university.urls import urlpatterns as application_patterns
from .health import readiness

urlpatterns = [path("ready/", readiness), *application_patterns]
