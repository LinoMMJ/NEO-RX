"""
Admin Views — CRUD de usuarios para rol administrador.

Endpoints (solo rol=administrador):
- GET    /api/admin/users/           → Lista paginada con filtros
- POST   /api/admin/users/           → Crear usuario
- GET    /api/admin/users/<pk>/      → Detalle
- PUT    /api/admin/users/<pk>/      → Actualizar (rol, is_active, etc.)
- DELETE /api/admin/users/<pk>/      → Desactivar (soft delete)
- POST   /api/admin/users/<pk>/reset-password/ → Reset password
"""

from django.contrib.auth import get_user_model
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import CustomUser
from .serializers import CustomUserSerializer

User = get_user_model()


class IsAdminUser(IsAuthenticated):
    """Permiso: solo usuarios con rol=administrador."""
    def has_permission(self, request, view):
        return super().has_permission(request, view) and getattr(request.user, "rol", None) == "administrador"


class AdminUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para gestión de usuarios por administradores.
    """
    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = CustomUserSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["rol", "is_active"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["username", "email", "date_joined", "last_login"]
    ordering = ["-date_joined"]

    def get_queryset(self):
        qs = super().get_queryset()
        # Excluir superusuarios del listado administrativo (se gestionan por Django admin)
        return qs.filter(is_superuser=False)

    def perform_create(self, serializer):
        # Crear usuario con password temporal si no se provee
        password = self.request.data.get("password") or "changeme123"
        user = serializer.save()
        user.set_password(password)
        user.save()
        return user

    @action(detail=True, methods=["post"])
    def reset_password(self, request, pk=None):
        """Genera nueva password temporal y la retorna (solo una vez)."""
        user = self.get_object()
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits + "!@#$%"
        new_pass = "".join(secrets.choice(alphabet) for _ in range(12))
        user.set_password(new_pass)
        user.save()
        return Response({
            "message": "Password reseteada",
            "temporary_password": new_pass,
            "username": user.username,
        })

    @action(detail=True, methods=["post"])
    def toggle_active(self, request, pk=None):
        """Activa/desactiva usuario (soft delete)."""
        user = self.get_object()
        user.is_active = not user.is_active
        user.save()
        return Response({
            "message": f"Usuario {'activado' if user.is_active else 'desactivado'}",
            "is_active": user.is_active,
        })