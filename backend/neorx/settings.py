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
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-key-change-in-production")

DEBUG = os.getenv("DEBUG", "True") == "True"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

AUTH_USER_MODEL = "accounts.CustomUser"

# ─── Encriptación (django-cryptography) ──────────────────────────────────────
# Generar clave: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FERNET_KEYS = [os.getenv("FERNET_KEY")] if os.getenv("FERNET_KEY") else []

# ─── Apps ────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
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
    "django_cryptography",
    "django_ratelimit",
    "drf_spectacular",
    # Local apps
    "accounts",
    "pacientes",
    "estudios",
    "diagnostico",
    "informes",
    "django_extensions",
]

# ─── Middleware (orden importante) ───────────────────────────────────────────
MIDDLEWARE = [
    # Seguridad primero
    "django.middleware.security.SecurityMiddleware",
    # Logging estructurado (temprano para capturar todo)
    "neorx.security.StructuredLoggingMiddleware",
    # Headers de seguridad
    "neorx.security.SecurityHeadersMiddleware",
    # Sesiones y auth
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Rate limiting (django-ratelimit usa middleware opcional)
    "django_ratelimit.middleware.RateLimitMiddleware",
]

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

# ─── Database ────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ─── Password Validation ────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─── Internationalization ────────────────────────────────────────────────────
LANGUAGE_CODE = "es-bo"
TIME_ZONE = "America/La_Paz"
USE_I18N = True
USE_TZ = True

# ─── Static & Media ──────────────────────────────────────────────────────────
STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── DRF ─────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

# ─── CORS ────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")

# ─── Celery ──────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "America/La_Paz"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

# ─── Internationalization ────────────────────────────────────────────────────
LANGUAGE_CODE = "es-bo"
TIME_ZONE = "America/La_Paz"
USE_I18N = True
USE_TZ = True

# ─── Static & Media ──────────────────────────────────────────────────────────
STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── DRF Spectacular (OpenAPI/Swagger) ───────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "Neo RX API",
    "DESCRIPTION": "API para Plataforma de Diagnóstico Asistido por IA — Radiografías de Tórax",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/",
    "TAGS": [
        {"name": "auth", "description": "Autenticación JWT + RBAC"},
        {"name": "pacientes", "description": "Gestión de pacientes (CRUD, búsqueda CI)"},
        {"name": "estudios", "description": "Estudios radiológicos y carga DICOM"},
        {"name": "diagnostico", "description": "Inferencia CNN, Grad-CAM, niveles clínicos"},
        {"name": "informes", "description": "Generación, firma, export PDF/DICOM SR"},
        {"name": "admin", "description": "Administración de usuarios (solo administrador)"},
        {"name": "metrics", "description": "Métricas operativas dashboard"},
    ],
    "CONTACT": {"name": "Neo RX Team", "email": "soporte@neorx.bo"},
    "LICENSE": {"name": "Academic Use Only", "url": "https://neorx.bo/license"},
}

# ─── Rate Limiting ───────────────────────────────────────────────────────────
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"
RATELIMIT_RATE = "100/h"  # Default global
RATELIMIT_KEY = "ip"
RATELIMIT_BLOCK = True

# ─── Logging ─────────────────────────────────────────────────────────────────
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Try to use JSON formatter, fallback to verbose if pythonjsonlogger not available
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
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter" if JSON_FORMATTER_AVAILABLE else "logging.Formatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if JSON_FORMATTER_AVAILABLE else "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs/neorx.log",
            "maxBytes": 10_000_000,
            "backupCount": 10,
            "formatter": "json" if JSON_FORMATTER_AVAILABLE else "verbose",
        },
        "audit_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs/audit.log",
            "maxBytes": 10_000_000,
            "backupCount": 10,
            "formatter": "json" if JSON_FORMATTER_AVAILABLE else "verbose",
        },
    },
    "loggers": {
        "neorx.request": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "neorx.audit": {"handlers": ["console", "audit_file"], "level": "INFO", "propagate": False},
        "django": {"handlers": ["console"], "level": "WARNING"},
        "django.request": {"handlers": ["console", "file"], "level": "ERROR", "propagate": False},
    },
}

# ─── drf-spectacular ─────────────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "Neo RX API",
    "DESCRIPTION": "API para Plataforma de Diagnóstico Asistido por IA — Radiografías de Tórax",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/",
    "TAGS": [
        {"name": "auth", "description": "Autenticación JWT + RBAC"},
        {"name": "pacientes", "description": "Gestión de pacientes (CRUD, búsqueda CI)"},
        {"name": "estudios", "description": "Estudios radiológicos y carga DICOM"},
        {"name": "diagnostico", "description": "Inferencia CNN, Grad-CAM, niveles clínicos"},
        {"name": "informes", "description": "Generación, firma, export PDF/DICOM SR"},
        {"name": "admin", "description": "Administración de usuarios (solo administrador)"},
        {"name": "metrics", "description": "Métricas operativas dashboard"},
    ],
}

# ─── Celery ──────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "America/La_Paz"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

# ─── Internationalization ────────────────────────────────────────────────────
LANGUAGE_CODE = "es-bo"
TIME_ZONE = "America/La_Paz"
USE_I18N = True
USE_TZ = True

# ─── Static & Media ──────────────────────────────────────────────────────────
STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Rate Limiting ───────────────────────────────────────────────────────────
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"
RATELIMIT_RATE = "100/h"
RATELIMIT_KEY = "ip"
RATELIMIT_BLOCK = True

# ─── CORS ────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")

# ─── Celery ──────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "America/La_Paz"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

# ─── Internationalization ────────────────────────────────────────────────────
LANGUAGE_CODE = "es-bo"
TIME_ZONE = "America/La_Paz"
USE_I18N = True
USE_TZ = True

# ─── Static & Media ──────────────────────────────────────────────────────────
STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Rate Limiting ───────────────────────────────────────────────────────────
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"
RATELIMIT_RATE = "100/h"
RATELIMIT_KEY = "ip"
RATELIMIT_BLOCK = True

# ─── CORS ────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")

# ─── DRF Spectacular (OpenAPI/Swagger) ───────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "Neo RX API",
    "DESCRIPTION": "API para Plataforma de Diagnóstico Asistido por IA — Radiografías de Tórax",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/",
    "TAGS": [
        {"name": "auth", "description": "Autenticación JWT + RBAC"},
        {"name": "pacientes", "description": "Gestión de pacientes (CRUD, búsqueda CI)"},
        {"name": "estudios", "description": "Estudios radiológicos y carga DICOM"},
        {"name": "diagnostico", "description": "Inferencia CNN, Grad-CAM, niveles clínicos"},
        {"name": "informes", "description": "Generación, firma, export PDF/DICOM SR"},
        {"name": "admin", "description": "Administración de usuarios (solo administrador)"},
        {"name": "metrics", "description": "Métricas operativas dashboard"},
    ],
    "CONTACT": {"name": "Neo RX Team", "email": "soporte@neorx.bo"},
    "LICENSE": {"name": "Academic Use Only", "url": "https://neorx.bo/license"},
}

# ─── Rate Limiting ───────────────────────────────────────────────────────────
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"
RATELIMIT_RATE = "100/h"
RATELIMIT_KEY = "ip"
RATELIMIT_BLOCK = True