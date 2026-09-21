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
from rest_framework.pagination import PageNumberPagination


class AdminPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

from .serializers import CustomUserSerializer
from neorx.models import log_audit

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
    pagination_class = AdminPagination
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
        user = serializer.save()
        # Auditoría
        log_audit(
            self.request,
            action="create",
            resource_type="usuario",
            resource_id=str(user.pk),
            after={
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "rol": user.rol,
                "is_active": user.is_active,
            },
            metadata={"created_by": self.request.user.username if self.request.user.is_authenticated else "system"},
        )
        return user

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        log_audit(self.request, action="update", resource_type="usuario",
                  resource_id=str(instance.pk), after={"is_active": False})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        # Capturar estado antes
        before = {
            "username": instance.username,
            "email": instance.email,
            "first_name": instance.first_name,
            "last_name": instance.last_name,
            "rol": instance.rol,
            "is_active": instance.is_active,
        }
        response = super().update(request, *args, partial=partial, **kwargs)
        # Capturar estado después
        instance.refresh_from_db()
        after = {
            "username": instance.username,
            "email": instance.email,
            "first_name": instance.first_name,
            "last_name": instance.last_name,
            "rol": instance.rol,
            "is_active": instance.is_active,
        }
        # Auditoría
        log_audit(
            request,
            action="update",
            resource_type="usuario",
            resource_id=str(instance.pk),
            before=before,
            after=after,
            metadata={"updated_by": request.user.username if request.user.is_authenticated else "system"},
        )
        return response

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
        # Auditoría
        log_audit(
            request,
            action="update",
            resource_type="usuario",
            resource_id=str(user.pk),
            before={"password_changed": True},
            after={"password_reset": True},
            metadata={"reset_by": request.user.username if request.user.is_authenticated else "system"},
        )
        return Response({
            "message": "Password reseteada",
            "temporary_password": new_pass,
            "username": user.username,
        })

    @action(detail=True, methods=["post"])
    def toggle_active(self, request, pk=None):
        """Activa/desactiva usuario (soft delete)."""
        user = self.get_object()
        before_active = user.is_active
        user.is_active = not user.is_active
        user.save()
        # Auditoría
        log_audit(
            request,
            action="update",
            resource_type="usuario",
            resource_id=str(user.pk),
            before={"is_active": before_active},
            after={"is_active": user.is_active},
            metadata={"toggled_by": request.user.username if request.user.is_authenticated else "system"},
        )
        return Response({
            "message": f"Usuario {'activado' if user.is_active else 'desactivado'}",
            "is_active": user.is_active,
        })
