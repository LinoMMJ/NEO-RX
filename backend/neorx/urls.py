from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from estudios.media import PrivateMediaView
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import CustomTokenObtainPairView, CustomTokenRefreshView, LogoutView, RevokeTokensView
from accounts.views import PasswordResetRequestView, PasswordResetVerifyView, PasswordResetConfirmView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from .views_workspace import WorkspaceSummaryView, ActivityListView

@require_GET
def health_check(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("api/workspace/resumen/", WorkspaceSummaryView.as_view(), name="workspace-summary"),
    path("api/actividad/", ActivityListView.as_view(), name="activity-list"),
    path("admin/", admin.site.urls),
    path("media/<path:path>", PrivateMediaView.as_view(), name="private-media"),

    # Auth endpoints at /api/ level
    path("api/token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/logout/", LogoutView.as_view(), name="token_logout"),
    path("api/token/revoke/", RevokeTokensView.as_view(), name="token_revoke"),
    path("api/password/reset/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("api/password/reset/verify/", PasswordResetVerifyView.as_view(), name="password_reset_verify"),
    path("api/password/reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),

    # App endpoints
    path("api/pacientes/", include("pacientes.urls")),
    path("api/estudios/", include("estudios.urls")),
    path("api/diagnostico/", include("diagnostico.urls")),
    path("api/informes/", include("informes.urls")),
    path("api/admin/", include("accounts.urls")),  # Admin user management
    path("api/metrics/", include("neorx.metrics_urls")),

    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
