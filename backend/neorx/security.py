"""
Seguridad y Compliance — Encriptación, Logging, Rate Limiting, Headers.

Componentes:
1. EncryptedCIField — Fernet para CI; DICOM privado sin cifrado binario
2. StructuredLoggingMiddleware — Logging JSON con request_id
3. AuditLog — Modelo de auditoría inmutable (ver neorx.models.AuditLog)
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
from cryptography.fernet import Fernet

from neorx.models import AuditLog, log_audit, get_client_ip, redact_sensitive

# ──────────────────────────────────────────────────────────────────────────────
# 1. CAMPOS ENCRIPTADOS (PyCA cryptography)
# ──────────────────────────────────────────────────────────────────────────────

# Paciente.ci utiliza neorx.fields.EncryptedCIField y FERNET_KEY.
# El archivo DICOM no está cifrado; /media/ exige JWT y permiso de lectura.

# ──────────────────────────────────────────────────────────────────────────────
# 2. AUDIT LOG — Usar neorx.models.AuditLog y neorx.models.log_audit
# ──────────────────────────────────────────────────────────────────────────────

# El modelo AuditLog y la función log_audit están definidos en neorx.models
# Se importan arriba: from neorx.models import AuditLog, log_audit, get_client_ip, redact_sensitive

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
            "path": "/media/[PRIVATE]" if request.path.startswith("/media/") else request.path,
            "query_params": {key: "[REDACTED]" for key in request.GET},
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
            "path": "/media/[PRIVATE]" if request.path.startswith("/media/") else request.path,
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
FERNET_KEY = os.getenv("FERNET_KEY")  # Generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

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
