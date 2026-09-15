"""
Views de autenticación con rate limiting.

Endpoints:
- POST /api/token/           → Login (rate limited: 5/min por IP)
- POST /api/token/refresh/   → Refresh token (rate limited: 20/min por IP)
"""

from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .serializers import CustomTokenObtainPairSerializer


@method_decorator(ratelimit(key="ip", rate="5/m", block=True), name="post")
class CustomTokenObtainPairView(TokenObtainPairView):
    """Login con rate limiting: 5 intentos por minuto por IP."""
    serializer_class = CustomTokenObtainPairSerializer


@method_decorator(ratelimit(key="ip", rate="20/m", block=True), name="post")
class CustomTokenRefreshView(TokenRefreshView):
    """Refresh token con rate limiting: 20 requests por minuto por IP."""
    pass