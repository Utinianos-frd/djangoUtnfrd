from typing import Any
from rest_framework.request import Request
from rest_framework.serializers import Serializer
from app.users.models import Users
from ..models import Membership, Organization


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


def get_role(user: Users, organization: Organization) -> str | None:
    """Rol del usuario en esta organización puntual (owner/admin/member), o None si no es miembro."""
    membership = Membership.objects.filter(organization=organization, user=user).first()
    return membership.role if membership else None
