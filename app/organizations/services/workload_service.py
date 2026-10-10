from app.tasks.models import Task
from ..models import Organization, Group, GroupMembership, Membership
from .common import error, get_role

ACTIVE_STATUSES = (Task.Status.PENDING, Task.Status.IN_PROGRESS)


def _get_org_and_group(organization_id, group_id):
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return None, None
    group = Group.objects.filter(id=group_id, organization=organization).first()
    return organization, group


def _can_view_workload(user, organization, group):
    role = get_role(user, organization)
    if role in (Membership.Role.OWNER, Membership.Role.ADMIN):
        return True
    return GroupMembership.objects.filter(
        group=group, user=user, role=GroupMembership.Role.GROUP_LEAD,
    ).exists()


def tareas_activas_qs(user):
    return Task.objects.filter(assignees=user, status__in=ACTIVE_STATUSES).select_related('project').distinct()


def carga_activa(user):
    return tareas_activas_qs(user).count()


def clasificar(active_task_count, threshold):
    if active_task_count == 0:
        return 'available'
    if active_task_count >= threshold:
        return 'overloaded'
    return 'busy'


def _member_workload_resource(membership, threshold):
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


def obtener_panel_workload(request, organization_id, group_id):
    organization, group = _get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    if not _can_view_workload(request.user, organization, group):
        return error(403, "No tenés permiso para ver el workload de este grupo")

    memberships = GroupMembership.objects.filter(group=group).select_related('user')
    data = [_member_workload_resource(m, organization.overload_threshold) for m in memberships]
    return {"data": data}, 200


def obtener_detalle_miembro(request, organization_id, group_id, user_id):
    organization, group = _get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    if not _can_view_workload(request.user, organization, group):
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


def advertencias_de_asignacion(organization, group, assignee_ids):
    """RF-42/43: devuelve advertencias (no bloqueantes) para assignee_ids que queden sobrecargados,
    con miembros disponibles del mismo grupo como alternativa sugerida."""
    if not assignee_ids:
        return []

    threshold = organization.overload_threshold
    warnings = []

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
