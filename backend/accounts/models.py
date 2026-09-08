from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROL_CHOICES = [
        ("medico", "Médico Radiólogo"),
        ("tecnico", "Técnico Radiólogo"),
        ("administrador", "Administrador"),
    ]
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default="tecnico")

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_rol_display()})"
