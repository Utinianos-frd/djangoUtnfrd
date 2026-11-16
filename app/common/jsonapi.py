"""Helpers genéricos del formato JSON:API, compartidos por todas las apps.

Acá va solo lo que no sabe nada del dominio (organizaciones, grupos, tareas...): si algo necesita
importar modelos, no pertenece a este módulo.
"""
from typing import Any

from rest_framework.request import Request
from rest_framework.serializers import Serializer

ErrorResponse = tuple[dict[str, Any], int]

INVALID_BODY = "El body debe seguir la estructura JSON:API: { data: { type, attributes } }"


def error(status_code: int, detail: str) -> ErrorResponse:
    """Arma un error en formato JSON:API: { errors: [{ status, detail }] }."""
    return {"errors": [{"status": str(status_code), "detail": detail}]}, status_code


def extract_attributes(request: Request) -> dict[str, Any] | None:
    """Saca request.data['data']['attributes'] del body JSON:API, o None si no tiene esa forma."""
    try:
        return request.data['data']['attributes']
    except (KeyError, TypeError):
        return None


def serializer_errors(serializer: Serializer) -> list[dict[str, Any]]:
    """Convierte serializer.errors en el formato de error JSON:API, con source.pointer por campo."""
    return [
        {"status": "400", "source": {"pointer": f"/data/attributes/{field}"}, "detail": str(msgs[0])}
        for field, msgs in serializer.errors.items()
    ]


def parse_body(
    request: Request, serializer_class: type[Serializer], *, partial: bool = False,
) -> tuple[dict[str, Any], ErrorResponse | None]:
    """Extrae y valida el body JSON:API en un paso.

    Devuelve (validated_data, None) si todo está bien, o ({}, error) con el error listo para devolver:

        body, err = parse_body(request, CreateTaskSerializer)
        if err:
            return err
    """
    attributes = extract_attributes(request)
    if attributes is None:
        return {}, error(400, INVALID_BODY)
    serializer = serializer_class(data=attributes, partial=partial)
    if not serializer.is_valid():
        return {}, ({"errors": serializer_errors(serializer)}, 400)
    return serializer.validated_data, None
