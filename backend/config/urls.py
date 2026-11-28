from django.contrib import admin
from django.urls import path

from common.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    # API v1
    path("api/v1/health/", health),
]
