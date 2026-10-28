import uuid
from typing import Any, cast

from rest_framework.request import Request
from app.users.models import Users
from ..models import Organization, Membership
from ..serializers.create_organization_serializer import CreateOrganizationSerializer
from ..serializers.update_organization_serializer import UpdateOrganizationSerializer
from ..serializers.join_serializer import JoinSerializer
from .common import error, extract_attributes, serializer_errors, get_role


def _organization_resource(organization: Organization, role: str | None) -> dict[str, Any]:
    """Arma el recurso JSON:API de una Organization; 'role' es el rol del usuario que pide, no un campo del modelo."""
    return {
        "type": "organizations",
        "id": str(organization.id),
        "attributes": {
            "name": organization.name,
            "logo_url": organization.logo_url,
            "plan": organization.plan,
            "plan_status": organization.plan_status,
            "overload_threshold": organization.overload_threshold,
            "role": role,
        },
    }


def _organization_response(organization: Organization, user: Users) -> dict[str, Any]:
    """Resuelve el rol de 'user' en 'organization' y arma la response completa."""
    return {"data": _organization_resource(organization, get_role(user, organization))}


def _invite_response(organization: Organization) -> dict[str, Any]:
    """Recurso JSON:API del link de invitación actual de la organización."""
    return {
        "data": {
            "type": "invitations",
            "id": str(organization.invite_token),
            "attributes": {
                "token": str(organization.invite_token),
                "active": organization.invite_active,
            },
        }
    }


def crear_organizacion(request: Request) -> tuple[dict[str, Any], int]:
    """Crea la Organization y, en la misma operación, la Membership de owner del usuario que la crea (RF-08)."""
    user = cast(Users, request.user)
    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = CreateOrganizationSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    organization = Organization.objects.create(
        name=serializer.validated_data['name'],
        logo_url=serializer.validated_data.get('logo_url', ''),
    )
    Membership.objects.create(organization=organization, user=user, role=Membership.Role.OWNER)

    return _organization_response(organization, user), 201


def listar_organizaciones(request: Request) -> tuple[dict[str, Any], int]:
    """Organizaciones donde el usuario tiene una Membership, con su rol en cada una."""
    memberships = Membership.objects.filter(user=cast(Users, request.user)).select_related('organization')
    data = [_organization_resource(m.organization, m.role) for m in memberships]
    return {"data": data}, 200


def obtener_organizacion(request: Request, organization_id: int) -> tuple[dict[str, Any], int]:
    """Detalle de una organización; requiere ser miembro (cualquier rol)."""
    user = cast(Users, request.user)
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if get_role(user, organization) is None:
        return error(403, "No pertenecés a esta organización")

    return _organization_response(organization, user), 200


def actualizar_organizacion(request: Request, organization_id: int) -> tuple[dict[str, Any], int]:
    """PATCH parcial de name/logo_url/overload_threshold; solo el owner puede llamarlo."""
    user = cast(Users, request.user)
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if get_role(user, organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede modificar la organización")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = UpdateOrganizationSerializer(data=attributes, partial=True)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    changed = False
    if 'name' in serializer.validated_data:
        organization.name = serializer.validated_data['name']
        changed = True
    if 'overload_threshold' in serializer.validated_data:
        organization.overload_threshold = serializer.validated_data['overload_threshold']
        changed = True
    if 'logo_url' in serializer.validated_data:
        organization.logo_url = serializer.validated_data['logo_url']
        changed = True
    if changed:
        organization.save()

    return _organization_response(organization, user), 200


def eliminar_organizacion(request: Request, organization_id: int) -> tuple[dict[str, Any] | None, int]:
    """Borra la organización (y en cascada sus Membership/Group/GroupMembership/Project/...); solo owner."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if get_role(cast(Users, request.user), organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede eliminar la organización")

    organization.delete()
    return None, 204


def ver_invitacion(request: Request, organization_id: int) -> tuple[dict[str, Any], int]:
    """Muestra el token/estado del link de invitación; owner o admin."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if get_role(cast(Users, request.user), organization) not in (Membership.Role.OWNER, Membership.Role.ADMIN):
        return error(403, "No tenés permiso para ver el link de invitación")

    return _invite_response(organization), 200


def regenerar_invitacion(request: Request, organization_id: int) -> tuple[dict[str, Any], int]:
    """Invalida el token actual y genera uno nuevo; solo owner."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if get_role(cast(Users, request.user), organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede regenerar el link de invitación")

    organization.invite_token = uuid.uuid4()
    organization.invite_active = True
    organization.save()

    return _invite_response(organization), 200


def desactivar_invitacion(request: Request, organization_id: int) -> tuple[dict[str, Any], int]:
    """Apaga el link sin tocar el token (se puede reactivar regenerando); solo owner."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if get_role(cast(Users, request.user), organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede desactivar el link de invitación")

    organization.invite_active = False
    organization.save()

    return _invite_response(organization), 200


def unirse_a_organizacion(request: Request) -> tuple[dict[str, Any], int]:
    """Resuelve el token y crea una Membership(role='member') para quien se une (RF-11/12)."""
    user = cast(Users, request.user)
    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = JoinSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    token = serializer.validated_data['token']
    organization = Organization.objects.filter(invite_token=token, invite_active=True).first()
    if not organization:
        return error(404, "Link de invitación inválido o inactivo")

    membership, created = Membership.objects.get_or_create(
        organization=organization,
        user=user,
        defaults={'role': Membership.Role.MEMBER},
    )
    if not created:
        return error(409, "Ya pertenecés a esta organización")

    return _organization_response(organization, user), 201
