"""
URL configuration for UNO Project.
"""

from django.contrib import admin
from django.urls import include, path
from rooms.views import HealthCheckView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthCheckView.as_view(), name="health_check"),
    path("api/rooms/", include("rooms.urls")),
]
