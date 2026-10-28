from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..services.comment_service import listar_comentarios, crear_comentario


@extend_schema(
    tags=['Tasks'],
    summary='Comentar tarea (POST) / listar comentarios (GET)',
    description=(
        'RF-30. GET: cualquiera que pueda ver la tarea (group lead, owner/admin, o un contributor asignado). '
        'POST: solo el group lead del grupo, o un contributor asignado a esta tarea.'
    ),
)
@api_view(['GET', 'POST'])
def comments(request: Request, organization_id: int, group_id: int, project_id: int, task_id: int) -> Response:
    if request.method == 'POST':
        data, status = crear_comentario(request, organization_id, group_id, project_id, task_id)
    else:
        data, status = listar_comentarios(request, organization_id, group_id, project_id, task_id)
    return Response(data, status=status)
