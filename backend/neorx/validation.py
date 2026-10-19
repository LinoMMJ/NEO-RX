"""Validation helpers for user supplied plain text."""

import unicodedata

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
