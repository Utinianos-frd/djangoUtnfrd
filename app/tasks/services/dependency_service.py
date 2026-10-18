from app.organizations.models import GroupMembership
from ..models import Task, TaskDependency
from ..serializers.create_dependency_serializer import CreateDependencySerializer
from .common import error, extract_attributes, serializer_errors
from .task_service import _get_org_group_project, _is_group_lead, _is_org_overseer, _group_role


def _dependency_resource(dependency):
    return {
        "type": "task_dependencies",
        "id": str(dependency.id),
        "attributes": {
            "blocking_task_id": dependency.blocking_task_id,
            "blocking_task_title": dependency.blocking_task.title,
            "blocked_task_id": dependency.blocked_task_id,
            "blocked_task_title": dependency.blocked_task.title,
            "dependency_type": dependency.dependency_type,
        },
    }


def _creates_cycle(blocking_task_id, blocked_task_id):
    """¿Agregar blocking_task_id -> blocked_task_id cierra un ciclo? Equivale a preguntar si
    blocking_task_id ya es alcanzable siguiendo las dependencias existentes a partir de blocked_task_id."""
    visited = set()
    stack = [blocked_task_id]
    while stack:
        current = stack.pop()
        if current == blocking_task_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        next_ids = TaskDependency.objects.filter(blocking_task_id=current).values_list('blocked_task_id', flat=True)
        stack.extend(next_ids)
    return False


def crear_dependencia(request, organization_id, group_id, project_id):
    organization, group, project = _get_org_group_project(organization_id, group_id, project_id)
    if not project:
        return error(404, "Proyecto no encontrado")

    if not _is_group_lead(request.user, group):
        return error(403, "Solo el group lead puede agregar dependencias")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = CreateDependencySerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    blocking_id = serializer.validated_data['blocking_task_id']
    blocked_id = serializer.validated_data['blocked_task_id']
    dependency_type = serializer.validated_data['dependency_type']

    if blocking_id == blocked_id:
        return error(400, "Una tarea no puede depender de sí misma")

    blocking_task = Task.objects.filter(id=blocking_id, project=project).first()
    blocked_task = Task.objects.filter(id=blocked_id, project=project).first()
    if not blocking_task or not blocked_task:
        return error(404, "blocking_task_id y blocked_task_id deben ser tareas de este proyecto")

    if TaskDependency.objects.filter(blocking_task=blocking_task, blocked_task=blocked_task).exists():
        return error(409, "Ya existe una dependencia entre estas dos tareas")

    if _creates_cycle(blocking_id, blocked_id):
        return error(400, "Esa dependencia generaría un ciclo circular entre tareas")

    dependency = TaskDependency.objects.create(
        blocking_task=blocking_task,
        blocked_task=blocked_task,
        dependency_type=dependency_type,
    )
    return {"data": _dependency_resource(dependency)}, 201


def listar_dependencias(request, organization_id, group_id, project_id):
    organization, group, project = _get_org_group_project(organization_id, group_id, project_id)
    if not project:
        return error(404, "Proyecto no encontrado")

    all_dependencies = TaskDependency.objects.filter(blocking_task__project=project).select_related(
        'blocking_task', 'blocked_task',
    )

    if _is_org_overseer(request.user, organization) or _is_group_lead(request.user, group):
        dependencies = all_dependencies
    elif _group_role(request.user, group) == GroupMembership.Role.CONTRIBUTOR:
        dependencies = [
            d for d in all_dependencies
            if d.blocking_task.assignees.filter(id=request.user.id).exists()
            or d.blocked_task.assignees.filter(id=request.user.id).exists()
        ]
    else:
        return error(403, "No tenés acceso a este proyecto")

    return {"data": [_dependency_resource(d) for d in dependencies]}, 200


def eliminar_dependencia(request, organization_id, group_id, project_id, dependency_id):
    organization, group, project = _get_org_group_project(organization_id, group_id, project_id)
    if not project:
        return error(404, "Proyecto no encontrado")

    if not _is_group_lead(request.user, group):
        return error(403, "Solo el group lead puede eliminar dependencias")

    dependency = TaskDependency.objects.filter(id=dependency_id, blocking_task__project=project).first()
    if not dependency:
        return error(404, "Dependencia no encontrada")

    dependency.delete()
    return None, 204
