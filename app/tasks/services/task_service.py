from typing import Any, cast

from django.utils import timezone
from rest_framework.request import Request
from app.users.models import Users
from app.organizations.models import Organization, Group, Membership, GroupMembership
from app.organizations.services.workload_service import advertencias_de_asignacion
from ..models import Project, Task, TaskDependency
from ..serializers.create_task_serializer import CreateTaskSerializer
from ..serializers.update_task_serializer import UpdateTaskSerializer
from ..serializers.update_task_status_serializer import UpdateTaskStatusSerializer
from .common import error, extract_attributes, serializer_errors


def _org_role(user: Users, organization: Organization | None) -> str | None:
    """Rol del usuario en esta organización, o None si no es miembro."""
    membership = Membership.objects.filter(organization=organization, user=user).first()
    return membership.role if membership else None


def _group_role(user: Users, group: Group | None) -> str | None:
    """Rol del usuario en este grupo, o None si no pertenece."""
    membership = GroupMembership.objects.filter(group=group, user=user).first()
    return membership.role if membership else None


def _is_group_lead(user: Users, group: Group | None) -> bool:
    """True si el usuario es el group lead de este grupo puntual."""
    return _group_role(user, group) == GroupMembership.Role.GROUP_LEAD


def _is_org_overseer(user: Users, organization: Organization | None) -> bool:
    """True si el usuario es owner o admin de la organización (visibilidad total, no edición)."""
    return _org_role(user, organization) in (Membership.Role.OWNER, Membership.Role.ADMIN)


def _get_org_group_project(
    organization_id: int, group_id: int, project_id: int,
) -> tuple[Organization | None, Group | None, Project | None]:
    """Resuelve (organization, group, project) por id; cualquiera puede venir None si no existe."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return None, None, None
    group = Group.objects.filter(id=group_id, organization=organization).first()
    if not group:
        return organization, None, None
    project = Project.objects.filter(id=project_id, group=group).first()
    return organization, group, project


def _is_blocked(task: Task) -> bool:
    """Candado visual (RF-33): True si alguna dependencia FS pendiente le impide arrancar. FF no cuenta acá."""
    return TaskDependency.objects.filter(
        blocked_task=task, dependency_type=TaskDependency.Type.FINISH_TO_START,
    ).exclude(blocking_task__status=Task.Status.DONE).exists()


def _task_resource(task: Task) -> dict[str, Any]:
    """Recurso JSON:API de una Task, con 'blocked' calculado en el momento (ver _is_blocked)."""
    return {
        "type": "tasks",
        "id": str(task.id),
        "attributes": {
            "title": task.title,
            "description": task.description,
            "closed_at": task.closed_at.isoformat() if task.closed_at else None,
            "status": task.status,
            "project_id": task.project_id,
            "assignee_ids": list(task.assignees.values_list('id', flat=True)),
            "blocked": _is_blocked(task),
        },
    }


def _task_response(task: Task, warnings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Envuelve el recurso de tarea; agrega meta.warnings (RF-42/43) solo si hay alguna."""
    payload: dict[str, Any] = {"data": _task_resource(task)}
    if warnings:
        payload["meta"] = {"warnings": warnings}
    return payload


def _dependency_block_reason(task: Task, new_status: str) -> str | None:
    """Motivo de bloqueo (RF-33) si new_status viola alguna dependencia pendiente, o None si está OK."""
    if new_status == task.status:
        return None

    pending_blockers = TaskDependency.objects.filter(blocked_task=task).exclude(
        blocking_task__status=Task.Status.DONE,
    ).select_related('blocking_task')

    for dep in pending_blockers:
        if dep.dependency_type == TaskDependency.Type.FINISH_TO_START and new_status != Task.Status.PENDING:
            return (
                f"No se puede avanzar: depende de '{dep.blocking_task.title}' ({dep.get_dependency_type_display()}), "
                "que todavía no está completada"
            )
        if dep.dependency_type == TaskDependency.Type.FINISH_TO_FINISH and new_status == Task.Status.DONE:
            return (
                f"No se puede completar: depende de '{dep.blocking_task.title}' ({dep.get_dependency_type_display()}), "
                "que todavía no está completada"
            )
    return None


def _reopen_block_reason(task: Task, new_status: str) -> str | None:
    """Si se reabre una tarea 'done' y alguna dependiente FS ya arrancó, quedaría in_progress y bloqueada a la vez:
    se rechaza. Las dependientes que siguen en 'pending' simplemente vuelven a quedar bloqueadas."""
    if task.status != Task.Status.DONE or new_status == Task.Status.DONE:
        return None

    advanced_titles = list(
        Task.objects.filter(
            blocked_by__blocking_task=task,
            blocked_by__dependency_type=TaskDependency.Type.FINISH_TO_START,
        ).exclude(status=Task.Status.PENDING).order_by('id').values_list('title', flat=True)
    )
    if advanced_titles:
        titles = ", ".join(f"'{title}'" for title in advanced_titles)
        return f"No se puede reabrir: las tareas {titles} dependen de esta y ya avanzaron"
    return None


def _set_status(task: Task, new_status: str) -> None:
    """Cambia el status y mantiene closed_at: se fecha al pasar a DONE y se limpia si la tarea se reabre."""
    if new_status == Task.Status.DONE and task.status != Task.Status.DONE:
        task.closed_at = timezone.now()
    elif new_status != Task.Status.DONE:
        task.closed_at = None
    task.status = new_status


def _validate_assignee_ids(group: Group, assignee_ids: list[int]) -> tuple[dict[str, Any], int] | None:
    """Devuelve un error 400 si algún id no es miembro del grupo, o None si todos son válidos."""
    valid_ids = set(
        GroupMembership.objects.filter(group=group, user_id__in=assignee_ids).values_list('user_id', flat=True)
    )
    invalid_ids = set(assignee_ids) - valid_ids
    if invalid_ids:
        return error(400, f"Los siguientes usuarios no son miembros del grupo: {sorted(invalid_ids)}")
    return None


def crear_tarea(request: Request, organization_id: int, group_id: int, project_id: int) -> tuple[dict[str, Any], int]:
    """Crea la tarea y asigna de una (opcional); solo group lead (RF-25/26)."""
    user = cast(Users, request.user)
    organization, group, project = _get_org_group_project(organization_id, group_id, project_id)
    if not project or not group or not organization:
        return error(404, "Proyecto no encontrado")

    if not _is_group_lead(user, group):
        return error(403, "Solo el group lead puede crear tareas")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = CreateTaskSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    assignee_ids = serializer.validated_data.get('assignee_ids', [])
    invalid = _validate_assignee_ids(group, assignee_ids)
    if invalid:
        return invalid

    # Una tarea nueva todavía no tiene dependencias, así que _dependency_block_reason nunca la frenaría:
    # cualquier status válido se respeta tal cual. _set_status completa closed_at si nace en 'done'.
    task = Task(
        project=project,
        title=serializer.validated_data['title'],
        description=serializer.validated_data['description'],
    )
    _set_status(task, serializer.validated_data['status'])
    task.save()
    if assignee_ids:
        task.assignees.set(assignee_ids)

    warnings = advertencias_de_asignacion(organization, group, assignee_ids)
    return _task_response(task, warnings), 201


def listar_tareas(request: Request, organization_id: int, group_id: int, project_id: int) -> tuple[dict[str, Any], int]:
    """Group lead/owner/admin ven todas las tareas del proyecto; un contributor solo las suyas (RF-31)."""
    user = cast(Users, request.user)
    organization, group, project = _get_org_group_project(organization_id, group_id, project_id)
    if not project:
        return error(404, "Proyecto no encontrado")

    if _is_org_overseer(user, organization) or _is_group_lead(user, group):
        tasks = Task.objects.filter(project=project)
    elif _group_role(user, group) == GroupMembership.Role.CONTRIBUTOR:
        tasks = Task.objects.filter(project=project, assignees=user)
    else:
        return error(403, "No tenés acceso a este proyecto")

    return {"data": [_task_resource(t) for t in tasks.distinct()]}, 200


def _can_view_task(user: Users, organization: Organization | None, group: Group | None, task: Task) -> bool:
    """Owner/admin/group lead ven cualquiera; un contributor solo si está asignado a esta tarea."""
    if _is_org_overseer(user, organization) or _is_group_lead(user, group):
        return True
    return task.assignees.filter(id=user.id).exists()


def obtener_tarea(
    request: Request, organization_id: int, group_id: int, project_id: int, task_id: int,
) -> tuple[dict[str, Any], int]:
    """Detalle de una tarea; mismo criterio de visibilidad que listar_tareas."""
    organization, group, project = _get_org_group_project(organization_id, group_id, project_id)
    if not project:
        return error(404, "Proyecto no encontrado")

    task = Task.objects.filter(id=task_id, project=project).first()
    if not task:
        return error(404, "Tarea no encontrada")

    if not _can_view_task(cast(Users, request.user), organization, group, task):
        return error(403, "No tenés acceso a esta tarea")

    return {"data": _task_resource(task)}, 200


def actualizar_tarea(
    request: Request, organization_id: int, group_id: int, project_id: int, task_id: int,
) -> tuple[dict[str, Any], int]:
    """Group lead edita cualquier campo (RF-27); contributor asignado solo 'status' (RF-29), chequeando dependencias (RF-33)."""
    user = cast(Users, request.user)
    organization, group, project = _get_org_group_project(organization_id, group_id, project_id)
    if not project:
        return error(404, "Proyecto no encontrado")

    task = Task.objects.filter(id=task_id, project=project).first()
    if not task:
        return error(404, "Tarea no encontrada")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    if _is_group_lead(user, group):
        if not group:
            return error(404, "Grupo no encontrado")

        lead_serializer = UpdateTaskSerializer(data=attributes, partial=True)
        if not lead_serializer.is_valid():
            return {"errors": serializer_errors(lead_serializer)}, 400

        if 'assignee_ids' in lead_serializer.validated_data:
            invalid = _validate_assignee_ids(group, lead_serializer.validated_data['assignee_ids'])
            if invalid:
                return invalid

        if 'status' in lead_serializer.validated_data:
            new_status = lead_serializer.validated_data['status']
            block_reason = _dependency_block_reason(task, new_status) or _reopen_block_reason(task, new_status)
            if block_reason:
                return error(409, block_reason)

        for field in ('title', 'description'):
            if field in lead_serializer.validated_data:
                setattr(task, field, lead_serializer.validated_data[field])
        if 'status' in lead_serializer.validated_data:
            _set_status(task, lead_serializer.validated_data['status'])
        task.save()
        warnings: list[dict[str, Any]] = []
        if 'assignee_ids' in lead_serializer.validated_data:
            assignee_ids = lead_serializer.validated_data['assignee_ids']
            task.assignees.set(assignee_ids)
            warnings = advertencias_de_asignacion(organization, group, assignee_ids) if organization else []

        return _task_response(task, warnings), 200

    # Contributor: solo puede cambiar el status de sus propias tareas (RF-29), nada más.
    if not task.assignees.filter(id=user.id).exists():
        return error(403, "Solo podés modificar tareas que te fueron asignadas")

    if set(attributes.keys()) - {'status'}:
        return error(400, "Como contributor solo podés modificar el campo 'status'")

    status_serializer = UpdateTaskStatusSerializer(data=attributes)
    if not status_serializer.is_valid():
        return {"errors": serializer_errors(status_serializer)}, 400

    new_status = status_serializer.validated_data['status']
    block_reason = _dependency_block_reason(task, new_status) or _reopen_block_reason(task, new_status)
    if block_reason:
        return error(409, block_reason)

    _set_status(task, status_serializer.validated_data['status'])
    task.save()
    return {"data": _task_resource(task)}, 200


def eliminar_tarea(
    request: Request, organization_id: int, group_id: int, project_id: int, task_id: int,
) -> tuple[dict[str, Any] | None, int]:
    """Borra la tarea (y en cascada sus comentarios/dependencias); solo group lead (RF-28)."""
    organization, group, project = _get_org_group_project(organization_id, group_id, project_id)
    if not project:
        return error(404, "Proyecto no encontrado")

    task = Task.objects.filter(id=task_id, project=project).first()
    if not task:
        return error(404, "Tarea no encontrada")

    if not _is_group_lead(cast(Users, request.user), group):
        return error(403, "Solo el group lead puede eliminar tareas")

    task.delete()
    return None, 204
