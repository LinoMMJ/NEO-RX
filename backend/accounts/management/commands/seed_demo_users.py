"""Create the three local demonstration roles when explicitly enabled."""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crea usuarios de demostración idempotentes solo si NEORX_CREATE_DEMO_USERS=true."

    def handle(self, *args, **options):
        enabled = os.getenv("NEORX_CREATE_DEMO_USERS", "false").lower() == "true"
        if not enabled:
            self.stdout.write("Usuarios demo deshabilitados; no se modificaron cuentas.")
            return

        definitions = [
            {
                "username": "admin",
                "email": "admin@neorx.local",
                "role": "administrador",
                "password_env": "NEORX_ADMIN_PASSWORD",
                "first_name": "Administrador",
                "is_staff": True,
                "is_superuser": True,
            },
            {
                "username": "medico",
                "email": "medico@neorx.local",
                "role": "medico",
                "password_env": "NEORX_MEDICO_PASSWORD",
                "first_name": "Médico",
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "username": "recepcionista",
                "email": "recepcionista@neorx.local",
                "role": "recepcionista",
                "password_env": "NEORX_RECEPCIONISTA_PASSWORD",
                "first_name": "Recepcionista",
                "is_staff": False,
                "is_superuser": False,
            },
        ]
        missing = [item["password_env"] for item in definitions if not os.getenv(item["password_env"])]
        if missing:
            raise CommandError("Faltan contraseñas para usuarios demo: " + ", ".join(missing))

        User = get_user_model()
        for item in definitions:
            user, created = User.objects.get_or_create(
                username=item["username"],
                defaults={"email": item["email"]},
            )
            user.email = item["email"]
            user.first_name = item["first_name"]
            user.rol = item["role"]
            user.is_active = True
            user.is_staff = item["is_staff"]
            user.is_superuser = item["is_superuser"]
            user.set_password(os.environ[item["password_env"]])
            user.save()
            action = "creado" if created else "actualizado"
            self.stdout.write(self.style.SUCCESS(f"Usuario {item['username']} {action}."))
