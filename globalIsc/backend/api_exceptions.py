"""Stable, backwards-compatible error responses for the public API.

Older endpoints return native DRF validation dictionaries while newer clients
need a predictable code, message and field map.  The handler keeps the native
keys at the root during the migration, and adds the canonical representation in
``error``.  This avoids breaking existing forms while giving every consumer one
contract to adopt.
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


logger = logging.getLogger(__name__)


STATUS_CODES = {
    status.HTTP_400_BAD_REQUEST: "validation_error",
    status.HTTP_401_UNAUTHORIZED: "authentication_required",
    status.HTTP_403_FORBIDDEN: "permission_denied",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
}

DEFAULT_MESSAGES = {
    "validation_error": "Revise la información enviada.",
    "authentication_required": "Inicie sesión nuevamente para continuar.",
    "permission_denied": "No tiene permisos para realizar esta acción.",
    "not_found": "El recurso solicitado no está disponible.",
    "conflict": "No se pudo aplicar el cambio porque la información cambió.",
    "rate_limited": "Ha realizado demasiados intentos. Espere un momento.",
    "internal_error": "No fue posible completar la operación. Inténtelo nuevamente.",
}


def _first_message(value):
    """Return the first human-readable message from DRF's nested error tree."""
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, (list, tuple)):
        for item in value:
            message = _first_message(item)
            if message:
                return message
    if isinstance(value, dict):
        for key in ("detail", "message"):
            message = _first_message(value.get(key))
            if message:
                return message
        for item in value.values():
            message = _first_message(item)
            if message:
                return message
    return None


def api_exception_handler(exc, context):
    """Add the canonical error contract to every DRF failure response."""
    response = drf_exception_handler(exc, context)

    if response is None:
        request = context.get("request")
        logger.exception(
            "Unhandled API exception",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={"path": getattr(request, "path", "")},
        )
        response = Response(
            {"detail": DEFAULT_MESSAGES["internal_error"]},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    raw_data = response.data
    payload = dict(raw_data) if isinstance(raw_data, dict) else {"detail": raw_data}
    code = STATUS_CODES.get(response.status_code, "internal_error")
    message = _first_message(raw_data) or DEFAULT_MESSAGES[code]

    # Compatibility layer: legacy consumers can continue reading fields such
    # as `nombre`, `muestras` or `detail` from the root response while new code
    # consumes `error.code`, `error.message` and `error.fields` consistently.
    payload.setdefault("detail", message)
    payload.setdefault("code", code)
    payload["error"] = {
        "code": code,
        "message": message,
        "fields": raw_data if response.status_code == status.HTTP_400_BAD_REQUEST else {},
    }
    response.data = payload
    return response
