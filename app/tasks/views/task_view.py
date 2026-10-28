from typing import Any
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..services.task_service import (
    crear_tarea,
    listar_tareas,
    obtener_tarea,
    actualizar_tarea,
    eliminar_tarea,
)


@extend_schema(
    tags=['Tasks'],
    summary='Crear tarea (POST) / listar tareas del proyecto (GET)',
    description=(
        'POST requiere ser group lead del grupo dueño del proyecto. '
        'GET: group lead, owner u admin ven todas las tareas del proyecto; un contributor ve únicamente '
        'las que tiene asignadas (RF-31).'
    ),
)
@api_view(['GET', 'POST'])
def tasks(request: Request, organization_id: int, group_id: int, project_id: int) -> Response:
    if request.method == 'POST':
        data, status = crear_tarea(request, organization_id, group_id, project_id)
    else:
        data, status = listar_tareas(request, organization_id, group_id, project_id)
    return Response(data, status=status)


@extend_schema(
    tags=['Tasks'],
    summary='Ver (GET) / editar (PATCH) / eliminar (DELETE) una tarea',
    description=(
        'GET: group lead/owner/admin, o un contributor asignado a la tarea. '
        'PATCH: el group lead puede editar título, status y asignados; un contributor asignado solo puede '
        'cambiar el campo "status" de sus propias tareas (RF-29). '
        'DELETE: solo el group lead (RF-28).'
    ),
)
@api_view(['GET', 'PATCH', 'DELETE'])
def task_detail(request: Request, organization_id: int, group_id: int, project_id: int, task_id: int) -> Response:
    data: dict[str, Any] | None
    if request.method == 'GET':
        data, status = obtener_tarea(request, organization_id, group_id, project_id, task_id)
    elif request.method == 'PATCH':
        data, status = actualizar_tarea(request, organization_id, group_id, project_id, task_id)
    else:
        data, status = eliminar_tarea(request, organization_id, group_id, project_id, task_id)
    return Response(data, status=status)
