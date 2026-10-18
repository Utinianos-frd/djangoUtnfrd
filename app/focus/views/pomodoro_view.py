from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..services.pomodoro_service import iniciar_pomodoro, actualizar_pomodoro


@extend_schema(
    tags=['Focus'],
    summary='Iniciar un pomodoro de 25 minutos dentro de la sesión (RF-49)',
    description='task_id tiene que ser una de las tareas elegidas al iniciar la sesión.',
)
@api_view(['POST'])
def pomodoros(request, session_id):
    data, status = iniciar_pomodoro(request, session_id)
    return Response(data, status=status)


@extend_schema(
    tags=['Focus'],
    summary='Pausar / reanudar / cancelar / completar un pomodoro',
    description=(
        'RF-49/50/51. Body: { "data": { "attributes": { "action": "pause" | "resume" | "cancel" | '
        '"complete" } } }. Al completar, la response trae meta.suggested_break_minutes (5, o 15 cada '
        '4 pomodoros consecutivos completados).'
    ),
)
@api_view(['PATCH'])
def pomodoro_detail(request, session_id, pomodoro_id):
    data, status = actualizar_pomodoro(request, session_id, pomodoro_id)
    return Response(data, status=status)
