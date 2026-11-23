"""Validation helpers for user supplied plain text."""

import unicodedata
from datetime import date

from django.utils import timezone
from rest_framework import serializers


def clean_plain_text(value, *, max_length, field_name="texto", allow_newlines=False):
    """Normalize text and reject invisible control characters.

    Clinical notes remain plain text. HTML escaping is performed by React and
    Django templates at output time, which preserves medically meaningful
    symbols such as ``<`` while preventing them from becoming markup.
    """
    if not isinstance(value, str):
        raise serializers.ValidationError(f"{field_name.capitalize()} debe ser texto.")
    value = unicodedata.normalize("NFC", value).strip()
    allowed = {"\n", "\r", "\t"} if allow_newlines else set()
    if any(unicodedata.category(char) == "Cc" and char not in allowed for char in value):
        raise serializers.ValidationError(
            f"{field_name.capitalize()} contiene caracteres de control no permitidos."
        )
    if len(value) > max_length:
        raise serializers.ValidationError(
            f"{field_name.capitalize()} no puede superar {max_length} caracteres."
        )
    return value


def clean_person_name(value, *, max_length=100, field_name="nombre"):
    """Accept international names without accepting numbers or markup-like symbols."""
    value = clean_plain_text(value, max_length=max_length, field_name=field_name)
    if not value:
        raise serializers.ValidationError(f"{field_name.capitalize()} es obligatorio.")
    separators = {" ", "'", "’", "-", "."}
    if not any(unicodedata.category(char).startswith("L") for char in value):
        raise serializers.ValidationError(f"{field_name.capitalize()} debe contener letras.")
    if any(not unicodedata.category(char).startswith(("L", "M")) and char not in separators for char in value):
        raise serializers.ValidationError(
            f"{field_name.capitalize()} solo puede contener letras, espacios, apóstrofes, puntos o guiones."
        )
    return " ".join(value.split())


def clean_patient_identifier(value, *, max_length=20):
    value = clean_plain_text(value, max_length=max_length, field_name="identificador")
    if not value or not any(char.isalnum() for char in value):
        raise serializers.ValidationError("El identificador debe contener letras o números.")
    if any(not char.isalnum() and char not in {" ", ".", "_", "-"} for char in value):
        raise serializers.ValidationError(
            "El identificador solo puede contener letras, números, espacios, puntos, guiones o guion bajo."
        )
    return " ".join(value.split())


def clean_phone(value, *, max_length=20):
    value = clean_plain_text(value, max_length=max_length, field_name="teléfono")
    if not value:
        return ""
    if any(not char.isdigit() and char not in {" ", "+", "-", "(", ")"} for char in value):
        raise serializers.ValidationError(
            "El teléfono solo puede contener números, espacios, +, guiones o paréntesis."
        )
    digits = sum(char.isdigit() for char in value)
    if not 7 <= digits <= 15:
        raise serializers.ValidationError("El teléfono debe contener entre 7 y 15 dígitos.")
    if "+" in value and not value.startswith("+"):
        raise serializers.ValidationError("El signo + solo puede aparecer al inicio del teléfono.")
    if value.count("+") > 1:
        raise serializers.ValidationError("El teléfono contiene más de un signo +.")
    return value


def validate_birth_date(value, *, today=None, max_age=100):
    """Reject future dates and patients older than ``max_age`` completed years."""
    if not isinstance(value, date):
        raise serializers.ValidationError("Ingrese una fecha de nacimiento válida.")
    today = today or timezone.localdate()
    if value > today:
        raise serializers.ValidationError("La fecha de nacimiento no puede ser futura.")
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age > max_age:
        raise serializers.ValidationError(
            f"No se puede registrar una persona con más de {max_age} años."
        )
    return value
