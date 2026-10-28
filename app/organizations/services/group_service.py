from typing import Any, cast

from rest_framework.request import Request
from app.users.models import Users
from ..models import Organization, Group, GroupMembership, Membership
from ..serializers.create_group_serializer import CreateGroupSerializer
from ..serializers.update_group_serializer import UpdateGroupSerializer
from .common import error, extract_attributes, serializer_errors, get_role


def _group_resource(group: Group) -> dict[str, Any]:
    """Recurso JSON:API de un Group."""
    return {
        "type": "groups",
        "id": str(group.id),
        "attributes": {
            "name": group.name,
            "organization_id": group.organization_id,
        },
    }


def _can_view_group(user: Users, organization: Organization, group: Group) -> bool:
    """Owner/admin ven cualquier grupo (oversight); un member solo si tiene GroupMembership ahí."""
    role = get_role(user, organization)
    if role in (Membership.Role.OWNER, Membership.Role.ADMIN):
        return True
    return GroupMembership.objects.filter(group=group, user=user).exists()


def crear_grupo(request: Request, organization_id: int) -> tuple[dict[str, Any], int]:
    """Crea un Group dentro de la organización; solo owner (RF-14 bis)."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if get_role(cast(Users, request.user), organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede crear grupos")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = CreateGroupSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    group = Group.objects.create(organization=organization, name=serializer.validated_data['name'])
    return {"data": _group_resource(group)}, 201


def listar_grupos(request: Request, organization_id: int) -> tuple[dict[str, Any], int]:
    """Owner/admin ven todos los grupos de la organización; un member solo los suyos."""
    user = cast(Users, request.user)
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    role = get_role(user, organization)
    if role is None:
        return error(403, "No pertenecés a esta organización")

    if role in (Membership.Role.OWNER, Membership.Role.ADMIN):
        groups = Group.objects.filter(organization=organization)
    else:
        groups = Group.objects.filter(organization=organization, memberships__user=user)

    return {"data": [_group_resource(g) for g in groups]}, 200


def obtener_grupo(request: Request, organization_id: int, group_id: int) -> tuple[dict[str, Any], int]:
    """Detalle de un grupo; owner/admin o miembro de ese grupo."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    group = Group.objects.filter(id=group_id, organization=organization).first()
    if not group:
        return error(404, "Grupo no encontrado")

    if not _can_view_group(cast(Users, request.user), organization, group):
        return error(403, "No tenés acceso a este grupo")

    return {"data": _group_resource(group)}, 200


def actualizar_grupo(request: Request, organization_id: int, group_id: int) -> tuple[dict[str, Any], int]:
    """Renombra el grupo; solo owner."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    group = Group.objects.filter(id=group_id, organization=organization).first()
    if not group:
        return error(404, "Grupo no encontrado")

    if get_role(cast(Users, request.user), organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede modificar el grupo")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = UpdateGroupSerializer(data=attributes, partial=True)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    if 'name' in serializer.validated_data:
        group.name = serializer.validated_data['name']
        group.save()

    return {"data": _group_resource(group)}, 200


def eliminar_grupo(request: Request, organization_id: int, group_id: int) -> tuple[dict[str, Any] | None, int]:
    """Borra el grupo (y en cascada sus memberships/proyectos/tareas); solo owner (RF-16)."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    group = Group.objects.filter(id=group_id, organization=organization).first()
    if not group:
        return error(404, "Grupo no encontrado")

    if get_role(cast(Users, request.user), organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede eliminar el grupo")

    group.delete()
    return None, 204
