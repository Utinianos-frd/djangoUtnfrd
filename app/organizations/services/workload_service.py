from typing import Any, cast

from django.db.models import QuerySet
from rest_framework.request import Request
from app.users.models import Users
from app.tasks.models import Task
from ..models import Organization, Group, GroupMembership
from app.common.jsonapi import error
from ..access import Access, get_org_and_group

ACTIVE_STATUSES = (Task.Status.PENDING, Task.Status.IN_PROGRESS)  # 'done' no cuenta para la carga de nadie


def tareas_activas_qs(user: Users) -> QuerySet[Task]:
    """Tareas activas del usuario en TODOS los grupos donde participa — la carga es global (RF-40)."""
    return Task.objects.filter(assignees=user, status__in=ACTIVE_STATUSES).select_related('project').distinct()


def carga_activa(user: Users) -> int:
    """Cantidad de tareas activas del usuario, global (ver tareas_activas_qs)."""
    return tareas_activas_qs(user).count()


def clasificar(active_task_count: int, threshold: int) -> str:
    """Clasifica según el umbral de la organización: available (0) / busy / overloaded (>= threshold)."""
    if active_task_count == 0:
        return 'available'
    if active_task_count >= threshold:
        return 'overloaded'
    return 'busy'


def _member_workload_resource(membership: GroupMembership, threshold: int) -> dict[str, Any]:
    """Recurso JSON:API de la fila de workload de un miembro del grupo."""
    count = carga_activa(membership.user)
    return {
        "type": "workload",
        "id": str(membership.user_id),
        "attributes": {
            "user_id": membership.user_id,
            "username": membership.user.username,
            "group_role": membership.role,
            "active_task_count": count,
            "status": clasificar(count, threshold),
        },
    }


def obtener_panel_workload(request: Request, organization_id: int, group_id: int) -> tuple[dict[str, Any], int]:
    """Panel de carga de cada miembro del grupo (RF-39/40/41)."""
    user = cast(Users, request.user)
    organization, group = get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    if not Access(user, organization, group).can_view_workload:
        return error(403, "No tenés permiso para ver el workload de este grupo")

    memberships = GroupMembership.objects.filter(group=group).select_related('user')
    data = [_member_workload_resource(m, organization.overload_threshold) for m in memberships]
    return {"data": data}, 200


def obtener_detalle_miembro(
    request: Request, organization_id: int, group_id: int, user_id: int,
) -> tuple[dict[str, Any], int]:
    """Detalle de tareas activas de un miembro, incluso de otros grupos (RF-45)."""
    user = cast(Users, request.user)
    organization, group = get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    if not Access(user, organization, group).can_view_workload:
        return error(403, "No tenés permiso para ver el workload de este grupo")

    membership = GroupMembership.objects.filter(group=group, user_id=user_id).select_related('user').first()
    if not membership:
        return error(404, "El usuario no pertenece a este grupo")

    tasks = tareas_activas_qs(membership.user)
    active_tasks = [
        {
            "task_id": t.id,
            "title": t.title,
            "status": t.status,
            "project_id": t.project_id,
            "group_id": t.project.group_id,
        }
        for t in tasks
    ]

    return {
        "data": {
            "type": "workload",
            "id": str(user_id),
            "attributes": {
                "user_id": user_id,
                "username": membership.user.username,
                "active_task_count": len(active_tasks),
                "status": clasificar(len(active_tasks), organization.overload_threshold),
                "active_tasks": active_tasks,
            },
        }
    }, 200


def advertencias_de_asignacion(
    organization: Organization, group: Group, assignee_ids: list[int],
) -> list[dict[str, Any]]:
    """Advertencias no bloqueantes (RF-42) para assignees que queden sobrecargados, con alternativas (RF-43)."""
    if not assignee_ids:
        return []

    threshold = organization.overload_threshold
    warnings: list[dict[str, Any]] = []

    for user_id in assignee_ids:
        membership = GroupMembership.objects.filter(group=group, user_id=user_id).select_related('user').first()
        if not membership:
            continue
        count = carga_activa(membership.user)
        if clasificar(count, threshold) == 'overloaded':
            warnings.append({
                "user_id": user_id,
                "username": membership.user.username,
                "active_task_count": count,
                "detail": f"{membership.user.username} está sobrecargado/a ({count} tareas activas, umbral {threshold})",
            })

    if warnings:
        alternatives = []
        others = GroupMembership.objects.filter(group=group).exclude(user_id__in=assignee_ids).select_related('user')
        for m in others:
            if clasificar(carga_activa(m.user), threshold) == 'available':
                alternatives.append(m.user.username)
        for warning in warnings:
            warning["suggested_alternatives"] = alternatives[:3]

    return warnings
