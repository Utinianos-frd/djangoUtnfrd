from typing import Any
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..services.group_service import (
    crear_grupo,
    listar_grupos,
    obtener_grupo,
    actualizar_grupo,
    eliminar_grupo,
)


@extend_schema(
    tags=['Groups'],
    summary='Crear grupo (POST) / listar grupos de la organización (GET)',
    description='POST requiere ser owner. GET: owner y admin ven todos los grupos; member solo los suyos.',
)
@api_view(['GET', 'POST'])
def groups(request: Request, organization_id: int) -> Response:
    if request.method == 'POST':
        data, status = crear_grupo(request, organization_id)
    else:
        data, status = listar_grupos(request, organization_id)
    return Response(data, status=status)


@extend_schema(
    tags=['Groups'],
    summary='Ver (GET) / editar (PATCH) / eliminar (DELETE) un grupo',
    description='PATCH y DELETE requieren ser owner de la organización. GET requiere ser owner/admin o miembro del grupo.',
)
@api_view(['GET', 'PATCH', 'DELETE'])
def group_detail(request: Request, organization_id: int, group_id: int) -> Response:
    data: dict[str, Any] | None
    if request.method == 'GET':
        data, status = obtener_grupo(request, organization_id, group_id)
    elif request.method == 'PATCH':
        data, status = actualizar_grupo(request, organization_id, group_id)
    else:
        data, status = eliminar_grupo(request, organization_id, group_id)
    return Response(data, status=status)
