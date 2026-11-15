from typing import Any, cast

from rest_framework.request import Request
from app.users.models import Users
from app.organizations.models import Organization, Group
from ..models import Task, Comment
from ..serializers.create_comment_serializer import CreateCommentSerializer
from .common import error, extract_attributes, serializer_errors
from .task_service import _get_org_group_project, _can_view_task, _is_group_lead


def _comment_resource(comment: Comment) -> dict[str, Any]:
    """Recurso JSON:API de un Comment, con el username del autor embebido."""
    return {
        "type": "comments",
        "id": str(comment.id),
        "attributes": {
            "text": comment.text,
            "author_id": comment.author_id,
            "author_username": comment.author.username,
            "created_at": comment.created_at.isoformat(),
        },
    }

def _get_task(
    organization_id: int, group_id: int, project_id: int, task_id: int,
) -> tuple[Organization | None, Group | None, Task | None]:
    """Resuelve (organization, group, task) por id; task viene None si no existe en ese proyecto."""
    organization, group, project = _get_org_group_project(organization_id, group_id, project_id)
    if not project:
        return None, None, None
    task = Task.objects.filter(id=task_id, project=project).first()
    return organization, group, task


def listar_comentarios(
    request: Request, organization_id: int, group_id: int, project_id: int, task_id: int,
) -> tuple[dict[str, Any], int]:
    """Comentarios de la tarea, en orden cronológico; mismo criterio de visibilidad que ver la tarea."""
    organization, group, task = _get_task(organization_id, group_id, project_id, task_id)
    if not task:
        return error(404, "Tarea no encontrada")

    if not _can_view_task(cast(Users, request.user), organization, group, task):
        return error(403, "No tenés acceso a esta tarea")

    comments = task.comments.select_related('author')
    return {"data": [_comment_resource(c) for c in comments]}, 200


def crear_comentario(
    request: Request, organization_id: int, group_id: int, project_id: int, task_id: int,
) -> tuple[dict[str, Any], int]:
    """Group lead comenta cualquier tarea de su grupo; contributor solo si está asignado a ella (RF-30)."""
    user = cast(Users, request.user)
    organization, group, task = _get_task(organization_id, group_id, project_id, task_id)
    if not task:
        return error(404, "Tarea no encontrada")

    is_lead = _is_group_lead(user, group)
    is_assigned = task.assignees.filter(id=user.id).exists()
    if not (is_lead or is_assigned):
        return error(403, "Solo el group lead o un contributor asignado puede comentar esta tarea")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = CreateCommentSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    comment = Comment.objects.create(task=task, author=user, text=serializer.validated_data['text'])
    return {"data": _comment_resource(comment)}, 201
