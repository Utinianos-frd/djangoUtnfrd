from typing import Any, cast

from django.db import transaction
from rest_framework.request import Request
from app.tasks.models import Task
from app.users.models import Users
from ..models import Organization, Membership, GroupMembership
from ..serializers.update_member_role_serializer import UpdateMemberRoleSerializer
from app.common.jsonapi import error, parse_body
from ..access import Access
from .group_membership_service import quitar_asignaciones


def _member_resource(membership: Membership) -> dict[str, Any]:
    """Recurso JSON:API de una Membership, con el username embebido para no obligar al frontend a resolverlo aparte."""
    return {
        "type": "memberships",
        "id": str(membership.id),
        "attributes": {
            "user_id": membership.user_id,
            "username": membership.user.username,
            "role": membership.role,
        },
    }


def listar_miembros(request: Request, organization_id: int) -> tuple[dict[str, Any], int]:
    """Lista los miembros de la organización; visible para cualquier miembro, no solo owner/admin."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if not Access(cast(Users, request.user), organization).is_member:
        return error(403, "No pertenecés a esta organización")

    memberships = Membership.objects.filter(organization=organization).select_related('user')
    return {"data": [_member_resource(m) for m in memberships]}, 200


def cambiar_rol_miembro(request: Request, organization_id: int, user_id: int) -> tuple[dict[str, Any], int]:
    """Cambia el rol de un miembro (solo owner); asignar 'owner' traspasa el puesto y demueve al owner saliente a admin."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if not Access(cast(Users, request.user), organization).is_owner:
        return error(403, "Solo el owner puede cambiar roles")

    target = Membership.objects.filter(organization=organization, user_id=user_id).first()
    if not target:
        return error(404, "El usuario no pertenece a esta organización")

    body, err = parse_body(request, UpdateMemberRoleSerializer)
    if err:
        return err

    new_role = body['role']

    if target.role == Membership.Role.OWNER and new_role != Membership.Role.OWNER:
        return error(400, "No se puede quitar el rol de owner directamente: traspasalo asignando owner a otro miembro")

    if new_role == Membership.Role.OWNER:
        current_owner = Membership.objects.filter(
            organization=organization, role=Membership.Role.OWNER,
        ).exclude(id=target.id).first()
        if current_owner:
            current_owner.role = Membership.Role.ADMIN
            current_owner.save()

    target.role = new_role
    target.save()

    return {"data": _member_resource(target)}, 200


def eliminar_miembro(request: Request, organization_id: int, user_id: int) -> tuple[dict[str, Any] | None, int]:
    """Saca a un miembro de la organización (owner o admin); no se puede eliminar al owner directamente."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if not Access(cast(Users, request.user), organization).is_overseer:
        return error(403, "No tenés permiso para eliminar miembros")

    target = Membership.objects.filter(organization=organization, user_id=user_id).first()
    if not target:
        return error(404, "El usuario no pertenece a esta organización")

    if target.role == Membership.Role.OWNER:
        return error(400, "No se puede eliminar al owner: traspasá el rol primero")

    group_memberships = GroupMembership.objects.filter(group__organization=organization, user_id=user_id)
    if group_memberships.filter(role=GroupMembership.Role.GROUP_LEAD).exists():
        return error(400, "No se puede eliminar a un group lead: reasigná el liderazgo de su grupo primero")

    # Sin esto, quien sale de la organización seguía siendo miembro (o lead) de sus grupos y asignado a sus tareas.
    with transaction.atomic():
        quitar_asignaciones(user_id, Task.objects.filter(project__group__organization=organization))
        group_memberships.delete()
        target.delete()
    return None, 204
