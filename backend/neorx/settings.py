"""
Neo RX — Django Settings

Configuración base + seguridad, logging, rate limiting, encriptación.
"""

import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


# ─── Core ────────────────────────────────────────────────────────────────────

DEBUG = os.getenv("DEBUG", "True").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-dev-key-change-in-production"
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("SECRET_KEY es obligatoria cuando DEBUG=False.")

ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1",
).split(",")

# Django confía en HTTPS únicamente cuando la petición llega desde el proxy
# interno configurado por Neo RX. El healthcheck directo queda exento del
# redirect porque Gunicorn no termina TLS por sí mismo.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", str(not DEBUG)).lower() == "true"
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000" if not DEBUG else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Cookies de Django (admin y CSRF). La API clínica usa JWT en Authorization,
# pero estas cookies también deben estar protegidas en el despliegue intranet.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Strict"

# Un request solo puede adjuntar una radiografía. Los archivos grandes se
# escriben a disco temporal en lugar de permanecer completos en memoria.
DATA_UPLOAD_MAX_NUMBER_FILES = 1
DATA_UPLOAD_MAX_NUMBER_FIELDS = 40
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700

AUTH_USER_MODEL = "accounts.CustomUser"
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.locmem.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@neorx.local")


# ─── Encriptación ────────────────────────────────────────────────────────────

# Generar clave:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

FERNET_KEY = os.getenv("FERNET_KEY")

if FERNET_KEY:
    from cryptography.fernet import Fernet
    from django.core.exceptions import ImproperlyConfigured
    try:
        Fernet(FERNET_KEY.encode())
    except (ValueError, TypeError):
        raise ImproperlyConfigured("FERNET_KEY no tiene formato válido.") from None
else:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("FERNET_KEY es obligatoria; no hay fallback sin cifrado.")


# ─── Apps ───────────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    # Django
    "neorx.apps.NeorxConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "corsheaders",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    #"django_ratelimit",
    "drf_spectacular",
    "django_extensions",

    # Local apps
    "accounts",
    "pacientes",
    "estudios",
    "diagnostico",
    "informes",
]


# ─── Middleware ─────────────────────────────────────────────────────────────

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # Logging estructurado
    "neorx.security.StructuredLoggingMiddleware",

    # Headers de seguridad
    "neorx.security.SecurityHeadersMiddleware",

    # Sesiones
    "django.contrib.sessions.middleware.SessionMiddleware",

    # CORS
    "corsheaders.middleware.CorsMiddleware",

    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",

    # Autenticación
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # Rate limiting
    #"django_ratelimit.middleware.RatelimitMiddleware",
]


# ─── URLs / Templates ───────────────────────────────────────────────────────

ROOT_URLCONF = "neorx.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "neorx.wsgi.application"


# ─── Database ───────────────────────────────────────────────────────────────

if os.getenv("POSTGRES_HOST"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "neorx"),
        "USER": os.getenv("POSTGRES_USER", "neorx"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.environ["POSTGRES_HOST"],
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}


# ─── Password Validation ────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# ─── Internationalization ───────────────────────────────────────────────────

LANGUAGE_CODE = "es-bo"
TIME_ZONE = "America/La_Paz"

USE_I18N = True
USE_TZ = True


# ─── Static & Media ─────────────────────────────────────────────────────────

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ─── Django REST Framework ──────────────────────────────────────────────────

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),

    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),

    "DEFAULT_SCHEMA_CLASS": (
        "drf_spectacular.openapi.AutoSchema"
    ),

    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),

    "DEFAULT_PAGINATION_CLASS": (
        "rest_framework.pagination.PageNumberPagination"
    ),

    "PAGE_SIZE": 20,

    "EXCEPTION_HANDLER": "neorx.exceptions.custom_exception_handler",
}


# ─── JWT ────────────────────────────────────────────────────────────────────

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=8),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "CHECK_REVOKE_TOKEN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# ─── CORS ───────────────────────────────────────────────────────────────────

CORS_ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173",
).split(",")


# ─── Celery ─────────────────────────────────────────────────────────────────

CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    "redis://localhost:6379/0",
)

CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    "redis://localhost:6379/0",
)

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

CELERY_TIMEZONE = "America/La_Paz"
CELERY_TASK_TRACK_STARTED = True
# Desarrollo local: ejecutar el diagnóstico en el request para no depender de
# un worker Celery ausente. Producción puede configurar "celery" explícitamente.
NEORX_INFERENCE_MODE = os.getenv("NEORX_INFERENCE_MODE", "inline" if DEBUG else "celery").lower()
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("NEORX_CNN_SOFT_LIMIT", "90"))
CELERY_TASK_TIME_LIMIT = int(os.getenv("NEORX_CNN_TIME_LIMIT", "120"))
CELERY_TASK_ROUTES = {
    "diagnostico.tasks.procesar_imagen_cnn": {
        "queue": "cnn_inference",
        "routing_key": "cnn_inference",
    },
}


# ─── DRF Spectacular / Swagger ──────────────────────────────────────────────

SPECTACULAR_SETTINGS = {
    "TITLE": "Neo RX API",

    "DESCRIPTION": (
        "API para Plataforma de Diagnóstico "
        "Asistido por IA — Radiografías de Tórax"
    ),

    "VERSION": "1.0.0",

    "SERVE_INCLUDE_SCHEMA": False,

    "COMPONENT_SPLIT_REQUEST": True,

    "SCHEMA_PATH_PREFIX": r"/api/",

    "TAGS": [
        {
            "name": "auth",
            "description": "Autenticación JWT + RBAC",
        },
        {
            "name": "pacientes",
            "description": "Gestión de pacientes (CRUD, búsqueda CI)",
        },
        {
            "name": "estudios",
            "description": "Estudios radiológicos y carga DICOM",
        },
        {
            "name": "diagnostico",
            "description": "Inferencia CNN, Grad-CAM, niveles clínicos",
        },
        {
            "name": "informes",
            "description": "Generación, firma, export PDF/DICOM SR",
        },
        {
            "name": "admin",
            "description": "Administración de usuarios (solo administrador)",
        },
        {
            "name": "metrics",
            "description": "Métricas operativas dashboard",
        },
    ],

    "CONTACT": {
        "name": "Neo RX Team",
        "email": "soporte@neorx.bo",
    },

    "LICENSE": {
        "name": "Academic Use Only",
        "url": "https://neorx.bo/license",
    },
}


# ─── Rate Limiting ──────────────────────────────────────────────────────────

# Activo automáticamente fuera del desarrollo local.
#
# django-ratelimit necesita Redis o Memcached para funcionar
# correctamente. Como actualmente solo queremos levantar
# el proyecto localmente, no necesitamos Redis.

RATELIMIT_ENABLE = not DEBUG

RATELIMIT_RATE = "100/h"
RATELIMIT_KEY = "ip"
RATELIMIT_BLOCK = True


# ─── Cache ──────────────────────────────────────────────────────────────────

# No configuramos Redis aquí porque actualmente no lo estás usando
# para el desarrollo local.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "neorx-local-cache",
        "TIMEOUT": 60 * 60 * 12,
        "OPTIONS": {"MAX_ENTRIES": 256, "CULL_FREQUENCY": 4},
    }
}
GRADCAM_CACHE_TIMEOUT = 60 * 60 * 12


# ─── Logging ────────────────────────────────────────────────────────────────

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


# Intentar usar JSON formatter.
# Si pythonjsonlogger no está instalado, usar formatter normal.

try:
    import pythonjsonlogger.jsonlogger  # noqa: F401

    JSON_FORMATTER_AVAILABLE = True

except ImportError:
    JSON_FORMATTER_AVAILABLE = False


LOGGING = {
    "version": 1,

    "disable_existing_loggers": False,

    "formatters": {
        "json": {
            "()": (
                "pythonjsonlogger.jsonlogger.JsonFormatter"
                if JSON_FORMATTER_AVAILABLE
                else "logging.Formatter"
            ),
            "fmt": (
                "%(asctime)s %(levelname)s "
                "%(name)s %(message)s"
            ),
        },

        "verbose": {
            "format": (
                "{asctime} {levelname} "
                "{name} {message}"
            ),
            "style": "{",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": (
                "json"
                if JSON_FORMATTER_AVAILABLE
                else "verbose"
            ),
        },

        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs/neorx.log",
            "maxBytes": 10_000_000,
            "backupCount": 10,
            "formatter": (
                "json"
                if JSON_FORMATTER_AVAILABLE
                else "verbose"
            ),
        },

        "audit_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs/audit.log",
            "maxBytes": 10_000_000,
            "backupCount": 10,
            "formatter": (
                "json"
                if JSON_FORMATTER_AVAILABLE
                else "verbose"
            ),
        },
    },

    "loggers": {
        "neorx.request": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },

        "neorx.audit": {
            "handlers": ["console", "audit_file"],
            "level": "INFO",
            "propagate": False,
        },

        "django": {
            "handlers": ["console"],
            "level": "WARNING",
        },

        "django.request": {
            "handlers": ["console", "file"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# Remembered sessions have an absolute deadline; refresh rotation cannot extend it.
REMEMBER_SESSION_LIFETIME = timedelta(days=30)
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')
PASSWORD_RESET_URL = FRONTEND_URL + '/recuperar-contrasena'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_TIMEOUT = 15
