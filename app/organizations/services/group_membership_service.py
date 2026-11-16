from typing import Any, cast

from django.db import transaction
from django.db.models import QuerySet
from rest_framework.request import Request
from app.tasks.models import Task
from app.users.models import Users
from ..models import Group, GroupMembership, Membership
from ..serializers.add_group_member_serializer import AddGroupMemberSerializer
from ..serializers.update_group_member_role_serializer import UpdateGroupMemberRoleSerializer
from app.common.jsonapi import error, parse_body
from ..access import Access, get_org_and_group


def _member_resource(membership: GroupMembership) -> dict[str, Any]:
    """Recurso JSON:API de una GroupMembership, con el username embebido."""
    return {
        "type": "group_memberships",
        "id": str(membership.id),
        "attributes": {
            "user_id": membership.user_id,
            "username": membership.user.username,
            "role": membership.role,
        },
    }


def quitar_asignaciones(user_id: int, tasks: QuerySet[Task]) -> None:
    """Desasigna al usuario de estas tareas. Se usa al sacarlo de un grupo/organización para que no queden
    asignaciones colgadas (que antes le seguían dando acceso a las tareas y sus comentarios)."""
    Task.assignees.through.objects.filter(task__in=tasks, users_id=user_id).delete()


def listar_miembros_grupo(request: Request, organization_id: int, group_id: int) -> tuple[dict[str, Any], int]:
    """Owner/admin, o cualquier miembro de este grupo puntual."""
    user = cast(Users, request.user)
    organization, group = get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    if not Access(user, organization, group).can_view_group:
        return error(403, "No tenés acceso a este grupo")

    memberships = GroupMembership.objects.filter(group=group).select_related('user')
    return {"data": [_member_resource(m) for m in memberships]}, 200


def agregar_miembro_grupo(request: Request, organization_id: int, group_id: int) -> tuple[dict[str, Any], int]:
    """Group lead agrega a un Member de la organización como contributor (RF-17)."""
    organization, group = get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    if not Access(cast(Users, request.user), organization, group).is_group_lead:
        return error(403, "Solo el group lead puede agregar miembros al grupo")

    body, err = parse_body(request, AddGroupMemberSerializer)
    if err:
        return err

    user_id = body['user_id']

    if not Membership.objects.filter(organization=organization, user_id=user_id).exists():
        return error(400, "El usuario debe ser miembro de la organización antes de sumarlo a un grupo")

    if GroupMembership.objects.filter(group=group, user_id=user_id).exists():
        return error(409, "El usuario ya pertenece a este grupo")

    membership = GroupMembership.objects.create(
        group=group, user_id=user_id, role=GroupMembership.Role.CONTRIBUTOR,
    )
    return {"data": _member_resource(membership)}, 201


def cambiar_rol_miembro_grupo(
    request: Request, organization_id: int, group_id: int, user_id: int,
) -> tuple[dict[str, Any], int]:
    """Owner asigna group_lead (RF-15); el lead saliente pasa a contributor. Bootstrapea la membership si no existía."""
    organization, group = get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    if not Access(cast(Users, request.user), organization).is_owner:
        return error(403, "Solo el owner puede asignar el rol de group lead")

    if not Membership.objects.filter(organization=organization, user_id=user_id).exists():
        return error(400, "El usuario debe ser miembro de la organización")

    body, err = parse_body(request, UpdateGroupMemberRoleSerializer)
    if err:
        return err

    new_role = body['role']

    # No usamos GroupMembership.objects.filter(...).first() seguido de un 404: el Owner puede asignar
    # el rol de group lead (RF-15) a alguien que todavía no tiene fila en este grupo — si no, nadie podría
    # llegar a ser el primer group lead (agregar_miembro_grupo exige ya ser group lead para agregar gente).
    target = GroupMembership.objects.filter(group=group, user_id=user_id).first()

    if target and target.role == GroupMembership.Role.GROUP_LEAD and new_role != GroupMembership.Role.GROUP_LEAD:
        return error(400, "No se puede quitar el rol de group lead directamente: asignaselo a otro miembro primero")

    if new_role == GroupMembership.Role.GROUP_LEAD:
        current_lead = GroupMembership.objects.filter(
            group=group, role=GroupMembership.Role.GROUP_LEAD,
        ).exclude(user_id=user_id).first()
        if current_lead:
            current_lead.role = GroupMembership.Role.CONTRIBUTOR
            current_lead.save()

    if target:
        target.role = new_role
        target.save()
    else:
        target = GroupMembership.objects.create(group=group, user_id=user_id, role=new_role)

    return {"data": _member_resource(target)}, 200


def eliminar_miembro_grupo(
    request: Request, organization_id: int, group_id: int, user_id: int,
) -> tuple[dict[str, Any] | None, int]:
    """Group lead saca a un miembro del grupo (RF-18); no se puede sacar al propio group lead."""
    organization, group = get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    if not Access(cast(Users, request.user), organization, group).is_group_lead:
        return error(403, "Solo el group lead puede eliminar miembros del grupo")

    target = GroupMembership.objects.filter(group=group, user_id=user_id).first()
    if not target:
        return error(404, "El usuario no pertenece a este grupo")

    if target.role == GroupMembership.Role.GROUP_LEAD:
        return error(400, "No se puede eliminar al group lead: reasigná el rol primero")

    with transaction.atomic():
        quitar_asignaciones(user_id, Task.objects.filter(project__group=group))
        target.delete()
    return None, 204
