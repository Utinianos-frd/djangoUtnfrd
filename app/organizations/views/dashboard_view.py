from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..services.dashboard_service import obtener_dashboard


@extend_schema(
    tags=['Dashboard'],
    summary='Panel de inicio del usuario',
    description=(
        'Agregados reales cruzados entre las organizaciones y grupos del usuario: grupos con su '
        'líder y conteos, total de miembros, tareas bloqueadas, carga del equipo, plan y actividad reciente.'
    ),
)
@api_view(['GET'])
def dashboard(request: Request) -> Response:
    data, status = obtener_dashboard(request)
    return Response(data, status=status)
