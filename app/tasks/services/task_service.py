from app.organizations.models import Organization, Group, Membership, GroupMembership
from ..models import Project, Task
from ..serializers.create_task_serializer import CreateTaskSerializer
from ..serializers.update_task_serializer import UpdateTaskSerializer
from ..serializers.update_task_status_serializer import UpdateTaskStatusSerializer
from .common import error, extract_attributes, serializer_errors


def _org_role(user, organization):
    membership = Membership.objects.filter(organization=organization, user=user).first()
    return membership.role if membership else None


def _group_role(user, group):
    membership = GroupMembership.objects.filter(group=group, user=user).first()
    return membership.role if membership else None


def _is_group_lead(user, group):
    return _group_role(user, group) == GroupMembership.Role.GROUP_LEAD


def _is_org_overseer(user, organization):
    return _org_role(user, organization) in (Membership.Role.OWNER, Membership.Role.ADMIN)


def _get_org_group_project(organization_id, group_id, project_id):
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return None, None, None
    group = Group.objects.filter(id=group_id, organization=organization).first()
    if not group:
        return organization, None, None
    project = Project.objects.filter(id=project_id, group=group).first()
    return organization, group, project


def _task_resource(task):
    return {
        "type": "tasks",
        "id": str(task.id),
        "attributes": {
            "title": task.title,
            "status": task.status,
            "project_id": task.project_id,
            "assignee_ids": list(task.assignees.values_list('id', flat=True)),
        },
    }


def _validate_assignee_ids(group, assignee_ids):
    valid_ids = set(
        GroupMembership.objects.filter(group=group, user_id__in=assignee_ids).values_list('user_id', flat=True)
    )
    invalid_ids = set(assignee_ids) - valid_ids
    if invalid_ids:
        return error(400, f"Los siguientes usuarios no son miembros del grupo: {sorted(invalid_ids)}")
    return None


def crear_tarea(request, organization_id, group_id, project_id):
    organization, group, project = _get_org_group_project(organization_id, group_id, project_id)
    if not project:
        return error(404, "Proyecto no encontrado")

    if not _is_group_lead(request.user, group):
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

    task = Task.objects.create(project=project, title=serializer.validated_data['title'])
    if assignee_ids:
        task.assignees.set(assignee_ids)

    return {"data": _task_resource(task)}, 201


def listar_tareas(request, organization_id, group_id, project_id):
    organization, group, project = _get_org_group_project(organization_id, group_id, project_id)
    if not project:
        return error(404, "Proyecto no encontrado")

    if _is_org_overseer(request.user, organization) or _is_group_lead(request.user, group):
        tasks = Task.objects.filter(project=project)
    elif _group_role(request.user, group) == GroupMembership.Role.CONTRIBUTOR:
        tasks = Task.objects.filter(project=project, assignees=request.user)
    else:
        return error(403, "No tenés acceso a este proyecto")

    return {"data": [_task_resource(t) for t in tasks.distinct()]}, 200


def _can_view_task(user, organization, group, task):
    if _is_org_overseer(user, organization) or _is_group_lead(user, group):
        return True
    return task.assignees.filter(id=user.id).exists()


def obtener_tarea(request, organization_id, group_id, project_id, task_id):
    organization, group, project = _get_org_group_project(organization_id, group_id, project_id)
    if not project:
        return error(404, "Proyecto no encontrado")

    task = Task.objects.filter(id=task_id, project=project).first()
    if not task:
        return error(404, "Tarea no encontrada")

    if not _can_view_task(request.user, organization, group, task):
        return error(403, "No tenés acceso a esta tarea")

    return {"data": _task_resource(task)}, 200


def actualizar_tarea(request, organization_id, group_id, project_id, task_id):
    organization, group, project = _get_org_group_project(organization_id, group_id, project_id)
    if not project:
        return error(404, "Proyecto no encontrado")

    task = Task.objects.filter(id=task_id, project=project).first()
    if not task:
        return error(404, "Tarea no encontrada")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    if _is_group_lead(request.user, group):
        serializer = UpdateTaskSerializer(data=attributes, partial=True)
        if not serializer.is_valid():
            return {"errors": serializer_errors(serializer)}, 400

        if 'assignee_ids' in serializer.validated_data:
            invalid = _validate_assignee_ids(group, serializer.validated_data['assignee_ids'])
            if invalid:
                return invalid

        if 'title' in serializer.validated_data:
            task.title = serializer.validated_data['title']
        if 'status' in serializer.validated_data:
            task.status = serializer.validated_data['status']
        task.save()
        if 'assignee_ids' in serializer.validated_data:
            task.assignees.set(serializer.validated_data['assignee_ids'])

        return {"data": _task_resource(task)}, 200

    # Contributor: solo puede cambiar el status de sus propias tareas (RF-29), nada más.
    if not task.assignees.filter(id=request.user.id).exists():
        return error(403, "Solo podés modificar tareas que te fueron asignadas")

    if set(attributes.keys()) - {'status'}:
        return error(400, "Como contributor solo podés modificar el campo 'status'")

    serializer = UpdateTaskStatusSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    task.status = serializer.validated_data['status']
    task.save()
    return {"data": _task_resource(task)}, 200


def eliminar_tarea(request, organization_id, group_id, project_id, task_id):
    organization, group, project = _get_org_group_project(organization_id, group_id, project_id)
    if not project:
        return error(404, "Proyecto no encontrado")

    task = Task.objects.filter(id=task_id, project=project).first()
    if not task:
        return error(404, "Tarea no encontrada")

    if not _is_group_lead(request.user, group):
        return error(403, "Solo el group lead puede eliminar tareas")

    task.delete()
    return None, 204
