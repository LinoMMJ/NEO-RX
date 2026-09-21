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
CELERY_TASK_TIME_LIMIT = 30 * 60


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
