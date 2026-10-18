from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..services.dependency_service import crear_dependencia, listar_dependencias, eliminar_dependencia


@extend_schema(
    tags=['Tasks'],
    summary='Crear dependencia (POST) / listar dependencias del proyecto (GET)',
    description=(
        'RF-32, RF-34, RF-37. POST requiere ser group lead; rechaza dependencias que generen ciclos '
        'circulares. GET devuelve el listado completo de dependencias del proyecto (las aristas del grafo '
        'de RF-37 — combinar con GET .../tasks para los nodos). Owner/admin/group lead ven todas; un '
        'contributor solo las que involucran alguna tarea asignada a él.'
    ),
)
@api_view(['GET', 'POST'])
def dependencies(request, organization_id, group_id, project_id):
    if request.method == 'POST':
        data, status = crear_dependencia(request, organization_id, group_id, project_id)
    else:
        data, status = listar_dependencias(request, organization_id, group_id, project_id)
    return Response(data, status=status)


@extend_schema(
    tags=['Tasks'],
    summary='Eliminar una dependencia (RF-36)',
    description='Solo el group lead.',
)
@api_view(['DELETE'])
def dependency_detail(request, organization_id, group_id, project_id, dependency_id):
    data, status = eliminar_dependencia(request, organization_id, group_id, project_id, dependency_id)
    return Response(data, status=status)
