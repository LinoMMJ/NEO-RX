from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROL_CHOICES = [
        ("medico", "Médico Radiólogo"),
        ("recepcionista", "Recepcionista"),
        ("administrador", "Administrador"),
    ]
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default="recepcionista")

    # Campos para restablecimiento de contraseña
    password_reset_token = models.CharField(max_length=64, blank=True, null=True)
    password_reset_expires = models.DateTimeField(blank=True, null=True)
    password_reset_attempts = models.PositiveSmallIntegerField(default=0)
    password_reset_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_rol_display()})"
