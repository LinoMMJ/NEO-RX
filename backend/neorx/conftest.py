"""
pytest configuration for Neo RX backend.
"""

import pytest
from django.conf import settings

# Configure pytest-django
pytest_plugins = ["pytest_django"]

def pytest_configure(config):
    """Configure Django settings for pytest."""
    from django.conf import settings
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.auth",
                "django.contrib.contenttypes",
                "django.contrib.sessions",
                "rest_framework",
                "rest_framework_simplejwt",
                "corsheaders",
                "django_cryptography",
                "django_ratelimit",
                "drf_spectacular",
                "accounts",
                "pacientes",
                "estudios",
                "diagnostico",
                "informes",
            ],
            AUTH_USER_MODEL="accounts.CustomUser",
            REST_FRAMEWORK={
                "DEFAULT_AUTHENTICATION_CLASSES": (
                    "rest_framework_simplejwt.authentication.JWTAuthentication",
                ),
                "DEFAULT_PERMISSION_CLASSES": (
                    "rest_framework.permissions.IsAuthenticated",
                ),
            },
            SECRET_KEY="test-secret-key-for-pytest",
            USE_TZ=True,
        )