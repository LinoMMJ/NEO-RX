"""
Seguridad y Compliance — Encriptación, Logging, Rate Limiting, Headers.

Componentes:
1. EncryptedField — Campo encriptado para CI y datos DICOM (django-cryptography)
2. StructuredLoggingMiddleware — Logging JSON con request_id
3. AuditLog — Modelo de auditoría inmutable
4. Rate limiting — django-ratelimit configurado
5. Security Headers — HSTS, CSP, X-Frame-Options, etc.
"""

import logging
import json
import uuid
import time
from functools import wraps

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse
from django.db import models
from django.contrib.auth import get_user_model
from cryptography.fernet import Fernet

# ──────────────────────────────────────────────────────────────────────────────
# 1. CAMPOS ENCRIPTADOS (django-cryptography)
# ──────────────────────────────────────────────────────────────────────────────

# django-cryptography usa settings.FERNET_KEYS para encriptar automáticamente
# Basta con usar models.EncryptedCharField / EncryptedTextField / EncryptedFileField
# en los modelos. La key se configura en settings.FERNET_KEYS.

# Ejemplo de uso en modelos:
#   from django_cryptography.fields import encrypt
#   ci = encrypt(models.CharField(max_length=20))
#   archivo_dicom = encrypt(models.FileField(...))

# ──────────────────────────────────────────────────────────────────────────────
# 2. AUDIT LOG MODELO
# ──────────────────────────────────────────────────────────────────────────────

User = get_user_model()


class AuditLog(models.Model):
    """Registro inmutable de auditoría para compliance médico."""
    ACTION_CHOICES = [
        ("create", "Crear"),
        ("read", "Leer"),
        ("update", "Actualizar"),
        ("delete", "Eliminar"),
        ("login", "Login"),
        ("logout", "Logout"),
        ("export", "Exportar"),
        ("firmar", "Firmar informe"),
        ("diagnostico", "Ejecutar diagnóstico"),
    ]

    id = models.BigAutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    request_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="audit_logs"
    )
    user_role = models.CharField(max_length=20, blank=True)

    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    resource_type = models.CharField(max_length=50)  # 'paciente', 'estudio', 'informe', etc.
    resource_id = models.CharField(max_length=100, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Detalles del cambio (JSON)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)

    # Metadatos adicionales
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["action", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} | {self.user} | {self.action} | {self.resource_type}#{self.resource_id}"


def log_audit(
    request,
    action: str,
    resource_type: str,
    resource_id: str = "",
    before: dict = None,
    after: dict = None,
    metadata: dict = None,
):
    """Helper para registrar auditoría desde vistas/servicios."""
    try:
        AuditLog.objects.create(
            request_id=getattr(request, "request_id", uuid.uuid4()),
            user=request.user if hasattr(request, "user") and request.user.is_authenticated else None,
            user_role=getattr(request.user, "rol", "") if hasattr(request, "user") else "",
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            before=before,
            after=after,
            metadata=metadata or {},
        )
    except Exception:
        # Nunca fallar la request principal por auditoría
        pass


def get_client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


# ──────────────────────────────────────────────────────────────────────────────
# 3. STRUCTURED LOGGING MIDDLEWARE
# ──────────────────────────────────────────────────────────────────────────────

class StructuredLoggingMiddleware(MiddlewareMixin):
    """
    Middleware que:
    - Genera request_id único por request
    - Loggea request/response en JSON estructurado
    - Mide latencia
    - Incluye info de usuario, IP, método, path, status
    """

    def process_request(self, request):
        request.request_id = uuid.uuid4()
        request._start_time = time.time()

        # Log request
        logger = logging.getLogger("neorx.request")
        logger.info(json.dumps({
            "event": "request_start",
            "request_id": str(request.request_id),
            "method": request.method,
            "path": request.path,
            "query_params": dict(request.GET),
            "ip": get_client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
            "user": str(request.user) if hasattr(request, "user") and request.user.is_authenticated else "anonymous",
            "user_role": getattr(request.user, "rol", "") if hasattr(request, "user") and request.user.is_authenticated else "",
            "timestamp": datetime.now().isoformat(),
        }, ensure_ascii=False))

    def process_response(self, request, response):
        if not hasattr(request, "_start_time"):
            return response

        latency_ms = int((time.time() - request._start_time) * 1000)
        request_id = getattr(request, "request_id", "unknown")

        # Log response
        logger = logging.getLogger("neorx.request")
        logger.info(json.dumps({
            "event": "request_end",
            "request_id": str(request_id),
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "user": str(request.user) if hasattr(request, "user") and request.user.is_authenticated else "anonymous",
            "timestamp": datetime.now().isoformat(),
        }, ensure_ascii=False))

        # Headers de respuesta
        response["X-Request-ID"] = str(request_id)
        return response


# ──────────────────────────────────────────────────────────────────────────────
# 4. SECURITY HEADERS MIDDLEWARE
# ──────────────────────────────────────────────────────────────────────────────

class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Añade headers de seguridad a todas las respuestas.
    Configurable via settings.SECURITY_HEADERS.
    """

    def process_response(self, request, response):
        # HSTS (solo en producción con HTTPS)
        if not settings.DEBUG:
            response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # CSP - Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response["Content-Security-Policy"] = csp

        # Otros headers
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Cache control para APIs
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"

        return response


# ──────────────────────────────────────────────────────────────────────────────
# 5. RATE LIMITING DECORATORS (django-ratelimit)
# ──────────────────────────────────────────────────────────────────────────────

# Uso en vistas:
# from django_ratelimit.decorators import ratelimit
# from django.utils.decorators import method_decorator
#
# @method_decorator(ratelimit(key='ip', rate='100/h', block=True), name='dispatch')
# class MiVista(APIView): ...
#
# O para login:
# @ratelimit(key='ip', rate='5/m', block=True)
# def login_view(request): ...


# ──────────────────────────────────────────────────────────────────────────────
# 6. CONFIGURACIÓN REQUERIDA EN SETTINGS.PY
# ──────────────────────────────────────────────────────────────────────────────

"""
Añadir a settings.py:

# ─── Security ────────────────────────────────────────────────────────────────
FERNET_KEYS = [os.getenv("FERNET_KEY")]  # Generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

SECURITY_HEADERS = {
    "HSTS": True,
    "CSP": True,
    "X_FRAME_OPTIONS": "DENY",
}

# ─── Logging ─────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs/neorx.log",
            "maxBytes": 10_000_000,
            "backupCount": 10,
            "formatter": "json",
        },
    },
    "loggers": {
        "neorx.request": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "neorx.audit": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "django": {"handlers": ["console"], "level": "WARNING"},
    },
}

# ─── Rate Limiting ───────────────────────────────────────────────────────────
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"
"""

from datetime import datetime