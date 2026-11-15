from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from ..services.seed_service import run_seed


@extend_schema(
    tags=['Dev'],
    summary='Poblar datos de prueba (solo DEBUG)',
    description=(
        'Crea (o reutiliza, si ya existen) una organización de demo (plan Pro) con un usuario por cada rol del '
        'sistema, dos grupos, proyectos, tareas en distintos estados, dependencias, comentarios y sesiones '
        'de Modo Foco. Devuelve un resumen y las credenciales generadas. '
        'Esta ruta solo existe cuando `DEBUG=True`; en cualquier otro ambiente no está registrada.'
    ),
    responses={
        200: OpenApiResponse(
            description='Datos de prueba listos',
            examples=[OpenApiExample(
                'Éxito',
                value={
                    'organization': 'Tasker Demo',
                    'groups': ['Backend', 'Frontend'],
                    'summary': {
                        'users': 8, 'projects': 4, 'tasks': 17,
                        'dependencies': 8, 'comments': 9, 'focus_sessions': 2,
                    },
                    'credentials': [
                        {'username': 'owner', 'password': 'owner123', 'org_role': 'owner', 'group_roles': {}},
                        {'username': 'grouplead', 'password': 'grouplead123', 'org_role': 'member',
                         'group_roles': {'Backend': 'group_lead'}},
                    ],
                },
                response_only=True,
                status_codes=['200'],
            )],
        ),
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def seed(request: Request) -> Response:
    data = run_seed()
    return Response(data, status=200)
