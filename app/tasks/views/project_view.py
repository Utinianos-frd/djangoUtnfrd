from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..services.project_service import (
    crear_proyecto,
    listar_proyectos,
    obtener_proyecto,
    actualizar_proyecto,
    eliminar_proyecto,
)


@extend_schema(
    tags=['Projects'],
    summary='Crear proyecto (POST) / listar proyectos del grupo (GET)',
    description='POST requiere ser owner de la organización. GET requiere ser owner/admin o miembro del grupo.',
)
@api_view(['GET', 'POST'])
def projects(request, organization_id, group_id):
    if request.method == 'POST':
        data, status = crear_proyecto(request, organization_id, group_id)
    else:
        data, status = listar_proyectos(request, organization_id, group_id)
    return Response(data, status=status)


@extend_schema(
    tags=['Projects'],
    summary='Ver (GET) / editar (PATCH) / eliminar (DELETE) un proyecto',
    description='PATCH y DELETE requieren ser owner de la organización. GET requiere ser owner/admin o miembro del grupo.',
)
@api_view(['GET', 'PATCH', 'DELETE'])
def project_detail(request, organization_id, group_id, project_id):
    if request.method == 'GET':
        data, status = obtener_proyecto(request, organization_id, group_id, project_id)
    elif request.method == 'PATCH':
        data, status = actualizar_proyecto(request, organization_id, group_id, project_id)
    else:
        data, status = eliminar_proyecto(request, organization_id, group_id, project_id)
    return Response(data, status=status)
