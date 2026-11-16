from typing import Any, cast

from rest_framework.request import Request
from app.users.models import Users
from ..models import Organization, Group
from ..serializers.create_group_serializer import CreateGroupSerializer
from ..serializers.update_group_serializer import UpdateGroupSerializer
from app.common.jsonapi import error, parse_body
from ..access import Access


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


def crear_grupo(request: Request, organization_id: int) -> tuple[dict[str, Any], int]:
    """Crea un Group dentro de la organización; solo owner (RF-14 bis)."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if not Access(cast(Users, request.user), organization).is_owner:
        return error(403, "Solo el owner puede crear grupos")

    body, err = parse_body(request, CreateGroupSerializer)
    if err:
        return err

    group = Group.objects.create(organization=organization, name=body['name'])
    return {"data": _group_resource(group)}, 201


def listar_grupos(request: Request, organization_id: int) -> tuple[dict[str, Any], int]:
    """Owner/admin ven todos los grupos de la organización; un member solo los suyos."""
    user = cast(Users, request.user)
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    access = Access(user, organization)
    if not access.is_member:
        return error(403, "No pertenecés a esta organización")

    if access.is_overseer:
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

    if not Access(cast(Users, request.user), organization, group).can_view_group:
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

    if not Access(cast(Users, request.user), organization).is_owner:
        return error(403, "Solo el owner puede modificar el grupo")

    body, err = parse_body(request, UpdateGroupSerializer, partial=True)
    if err:
        return err

    if 'name' in body:
        group.name = body['name']
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

    if not Access(cast(Users, request.user), organization).is_owner:
        return error(403, "Solo el owner puede eliminar el grupo")

    group.delete()
    return None, 204
