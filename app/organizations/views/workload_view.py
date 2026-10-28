from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..services.workload_service import obtener_panel_workload, obtener_detalle_miembro


@extend_schema(
    tags=['Workload'],
    summary='Panel de carga de trabajo del grupo',
    description=(
        'RF-39/40/41: carga activa de cada miembro del grupo (sumada en todos los grupos donde participa) '
        'y su clasificación (available/busy/overloaded) según el overload_threshold de la organización. '
        'Visible para owner, admin, o el group lead de este grupo.'
    ),
)
@api_view(['GET'])
def workload(request: Request, organization_id: int, group_id: int) -> Response:
    data, status = obtener_panel_workload(request, organization_id, group_id)
    return Response(data, status=status)


@extend_schema(
    tags=['Workload'],
    summary='Detalle de tareas activas de un miembro del grupo (RF-45)',
)
@api_view(['GET'])
def workload_member_detail(request: Request, organization_id: int, group_id: int, user_id: int) -> Response:
    data, status = obtener_detalle_miembro(request, organization_id, group_id, user_id)
    return Response(data, status=status)
