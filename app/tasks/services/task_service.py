from typing import Any, cast

from django.utils import timezone
from rest_framework.request import Request
from app.users.models import Users
from app.organizations.models import Organization, Group, GroupMembership
from app.organizations.services.workload_service import advertencias_de_asignacion
from ..models import Project, Task, TaskDependency
from ..serializers.create_task_serializer import CreateTaskSerializer
from ..serializers.update_task_serializer import UpdateTaskSerializer
from ..serializers.update_task_status_serializer import UpdateTaskStatusSerializer
from app.organizations.access import Access, get_org_and_group
from app.common.jsonapi import INVALID_BODY, error, extract_attributes, serializer_errors, parse_body


def _get_org_group_project(
    organization_id: int, group_id: int, project_id: int,
) -> tuple[Organization | None, Group | None, Project | None]:
    """Resuelve (organization, group, project) por id; cualquiera puede venir None si no existe."""
    organization, group = get_org_and_group(organization_id, group_id)
    if not organization or not group:
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
                f"No se puede avanzar: depende de '{dep.blocking_task.title}' (finish-to-start), "
                "que todavía no está completada"
            )
        if dep.dependency_type == TaskDependency.Type.FINISH_TO_FINISH and new_status == Task.Status.DONE:
            return (
                f"No se puede completar: depende de '{dep.blocking_task.title}' (finish-to-finish), "
                "que todavía no está completada"
            )
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

    if not Access(user, organization, group).is_group_lead:
        return error(403, "Solo el group lead puede crear tareas")

    body, err = parse_body(request, CreateTaskSerializer)
    if err:
        return err

    assignee_ids = body.get('assignee_ids', [])
    invalid = _validate_assignee_ids(group, assignee_ids)
    if invalid:
        return invalid

    task = Task.objects.create(
        project=project,
        title=body['title'],
        description=body['description'],
    )
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

    access = Access(user, organization, group)
    if access.sees_all_tasks:
        tasks = Task.objects.filter(project=project)
    elif access.is_contributor:
        tasks = Task.objects.filter(project=project, assignees=user)
    else:
        return error(403, "No tenés acceso a este proyecto")

    return {"data": [_task_resource(t) for t in tasks.distinct()]}, 200


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

    if not Access(cast(Users, request.user), organization, group).can_view_task(task):
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
        return error(400, INVALID_BODY)

    access = Access(user, organization, group)
    if access.is_group_lead:
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
            block_reason = _dependency_block_reason(task, lead_serializer.validated_data['status'])
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
    if not access.is_active_assignee(task):
        return error(403, "Solo podés modificar tareas que te fueron asignadas")

    if set(attributes.keys()) - {'status'}:
        return error(400, "Como contributor solo podés modificar el campo 'status'")

    status_serializer = UpdateTaskStatusSerializer(data=attributes)
    if not status_serializer.is_valid():
        return {"errors": serializer_errors(status_serializer)}, 400

    block_reason = _dependency_block_reason(task, status_serializer.validated_data['status'])
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

    if not Access(cast(Users, request.user), organization, group).is_group_lead:
        return error(403, "Solo el group lead puede eliminar tareas")

    task.delete()
    return None, 204
