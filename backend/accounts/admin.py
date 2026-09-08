from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Rol", {"fields": ("rol",)}),
    )
    list_display = ("username", "email", "first_name", "last_name", "rol", "is_staff")
    list_filter = UserAdmin.list_filter + ("rol",)
