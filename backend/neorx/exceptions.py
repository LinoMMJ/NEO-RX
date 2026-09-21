"""
Manejador centralizado de excepciones para Django REST Framework.

Estandariza las respuestas de error y evita exponer información sensible.
"""

import logging
from rest_framework.views import exception_handler
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger("neorx.request")


def custom_exception_handler(exc, context):
    """
    Manejador centralizado de excepciones para DRF.

    Estructura de respuesta estándar:
    {
        "status": 400,
        "title": "Bad Request",
        "detail": "Descripción del error",
        "errors": {...}  # opcional, para errores de validación
    }
    """
    # Llamar al handler por defecto de DRF primero
    response = exception_handler(exc, context)

    if response is not None:
        # Estructurar respuesta de error estándar
        custom_data = {
            "status": response.status_code,
            "title": _get_error_title(response.status_code),
            "detail": _get_error_detail(response.data),
        }

        # Agregar errores de validación si existen
        if isinstance(response.data, dict) and not isinstance(response.data.get("detail"), str):
            # Errores de validación serializador
            errors = _flatten_errors(response.data)
            if errors:
                custom_data["errors"] = errors

        if isinstance(response.data, dict) and "error" in response.data:
            custom_data["error"] = response.data["error"]
        response.data = custom_data
        return response

    # Excepción no manejada por DRF (500)
    logger.exception("Excepción no manejada: %s", exc)
    return Response(
        {
            "status": 500,
            "title": "Internal Server Error",
            "detail": "Error interno del servidor. Contacte al administrador.",
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _get_error_title(status_code):
    """Mapea códigos HTTP a títulos descriptivos."""
    titles = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        413: "Payload Too Large",
        422: "Unprocessable Entity",
        500: "Internal Server Error",
    }
    return titles.get(status_code, "Error")


def _get_error_detail(data):
    """Extrae mensaje de error legible del data de DRF."""
    if isinstance(data, dict):
        if "detail" in data:
            return str(data["detail"])
        if "detail" in str(data).lower():
            # Buscar en valores anidados
            for v in data.values():
                if isinstance(v, list) and v:
                    return str(v[0])
                if isinstance(v, str):
                    return v
    return "Error en la solicitud"


def _flatten_errors(data, prefix=""):
    """Aplana errores de validación anidados."""
    errors = {}
    for key, value in data.items():
        if isinstance(value, list):
            errors[f"{prefix}{key}"] = [str(v) for v in value]
        elif isinstance(value, dict):
            nested = _flatten_errors(value, f"{prefix}{key}.")
            errors.update(nested)
        else:
            errors[f"{prefix}{key}"] = str(value)
    return errors
