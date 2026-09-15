from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_admin import AdminUserViewSet

router = DefaultRouter()
router.register(r"users", AdminUserViewSet, basename="admin-user")

urlpatterns = [
    path("", include(router.urls)),
]