from typing import Any

from rest_framework.request import Request
from rest_framework.serializers import Serializer


def error(status_code: int, detail: str) -> tuple[dict[str, Any], int]:
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
