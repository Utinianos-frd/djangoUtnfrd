from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..services.membership_service import listar_miembros, cambiar_rol_miembro, eliminar_miembro


@extend_schema(
    tags=['Organizations'],
    summary='Listar miembros de la organización',
    description='Requiere ser miembro de la organización (cualquier rol).',
)
@api_view(['GET'])
def members(request, organization_id):
    data, status = listar_miembros(request, organization_id)
    return Response(data, status=status)


@extend_schema(
    tags=['Organizations'],
    summary='Cambiar el rol de un miembro (PATCH) / eliminarlo (DELETE)',
    description=(
        'PATCH requiere ser owner. Asignar role="owner" traspasa la propiedad: el owner saliente pasa '
        'a admin automáticamente. No se puede bajar al owner actual a otro rol directamente. '
        'DELETE requiere ser owner o admin; no se puede eliminar al owner.'
    ),
)
@api_view(['PATCH', 'DELETE'])
def member_detail(request, organization_id, user_id):
    if request.method == 'PATCH':
        data, status = cambiar_rol_miembro(request, organization_id, user_id)
    else:
        data, status = eliminar_miembro(request, organization_id, user_id)
    return Response(data, status=status)
