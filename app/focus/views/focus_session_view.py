from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..services.focus_session_service import iniciar_sesion, obtener_sesion_activa, finalizar_sesion


@extend_schema(
    tags=['Focus'],
    summary='Iniciar una sesión de modo foco (RF-46, RF-47)',
    description=(
        'Requiere que cada tarea en task_ids esté asignada al usuario y que la organización dueña '
        'esté en plan Pro (sección 8.4 del documento). Solo puede haber una sesión activa por usuario.'
    ),
)
@api_view(['POST'])
def focus_sessions(request: Request) -> Response:
    data, status = iniciar_sesion(request)
    return Response(data, status=status)


@extend_schema(
    tags=['Focus'],
    summary='Ver mi sesión de modo foco activa',
    description='Si no hay sesión activa devuelve 200 con {"data": null}.',
)
@api_view(['GET'])
def active_focus_session(request: Request) -> Response:
    data, status = obtener_sesion_activa(request)
    return Response(data, status=status)


@extend_schema(
    tags=['Focus'],
    summary='Terminar la sesión y ver el resumen (RF-53)',
    description='Tiempo trabajado, pomodoros completados, y tareas de la sesión que quedaron en status done.',
)
@api_view(['POST'])
def end_focus_session(request: Request, session_id: int) -> Response:
    data, status = finalizar_sesion(request, session_id)
    return Response(data, status=status)
