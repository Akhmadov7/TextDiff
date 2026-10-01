from django.contrib import admin
from django.urls import include, path

from api.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),  # login/logout, шаблон — templates/registration/
    path("api/", api.urls),  # Swagger UI: /api/docs
    path("", include("web.urls")),
]
