from django.utils import timezone
from ..models import FocusSession, Pomodoro
from ..serializers.start_pomodoro_serializer import StartPomodoroSerializer
from ..serializers.pomodoro_action_serializer import PomodoroActionSerializer
from .common import error, extract_attributes, serializer_errors
from .focus_session_service import get_own_session


def _pomodoro_resource(pomodoro):
    return {
        "type": "pomodoros",
        "id": str(pomodoro.id),
        "attributes": {
            "task_id": pomodoro.task_id,
            "status": pomodoro.status,
            "duration_minutes": Pomodoro.DURATION_MINUTES,
            "started_at": pomodoro.started_at.isoformat(),
            "completed_at": pomodoro.completed_at.isoformat() if pomodoro.completed_at else None,
        },
    }


def _consecutive_completed_count(session):
    count = 0
    for pomodoro in session.pomodoros.order_by('-started_at'):
        if pomodoro.status != Pomodoro.Status.COMPLETED:
            break
        count += 1
    return count


def iniciar_pomodoro(request, session_id):
    session = get_own_session(request.user, session_id)
    if not session:
        return error(404, "Sesión no encontrada")
    if session.status != FocusSession.Status.ACTIVE:
        return error(409, "Esta sesión ya terminó")

    if Pomodoro.objects.filter(
        session=session, status__in=[Pomodoro.Status.RUNNING, Pomodoro.Status.PAUSED],
    ).exists():
        return error(409, "Ya hay un pomodoro en curso en esta sesión")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = StartPomodoroSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    task_id = serializer.validated_data['task_id']
    if not session.tasks.filter(id=task_id).exists():
        return error(400, "Esa tarea no forma parte del objetivo de esta sesión")

    pomodoro = Pomodoro.objects.create(session=session, task_id=task_id)
    return {"data": _pomodoro_resource(pomodoro)}, 201


def actualizar_pomodoro(request, session_id, pomodoro_id):
    session = get_own_session(request.user, session_id)
    if not session:
        return error(404, "Sesión no encontrada")

    pomodoro = Pomodoro.objects.filter(id=pomodoro_id, session=session).first()
    if not pomodoro:
        return error(404, "Pomodoro no encontrado")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = PomodoroActionSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    action = serializer.validated_data['action']
    now = timezone.now()

    if action == 'pause':
        if pomodoro.status != Pomodoro.Status.RUNNING:
            return error(409, "Solo se puede pausar un pomodoro que está corriendo")
        pomodoro.status = Pomodoro.Status.PAUSED
        pomodoro.paused_at = now

    elif action == 'resume':
        if pomodoro.status != Pomodoro.Status.PAUSED:
            return error(409, "Solo se puede reanudar un pomodoro pausado")
        pomodoro.total_paused_seconds += int((now - pomodoro.paused_at).total_seconds())
        pomodoro.paused_at = None
        pomodoro.status = Pomodoro.Status.RUNNING

    elif action == 'cancel':
        if pomodoro.status in (Pomodoro.Status.COMPLETED, Pomodoro.Status.CANCELLED):
            return error(409, "Este pomodoro ya terminó")
        pomodoro.status = Pomodoro.Status.CANCELLED

    else:  # complete
        if pomodoro.status != Pomodoro.Status.RUNNING:
            return error(
                409,
                "Solo se puede completar un pomodoro que está corriendo (reanudalo primero si está pausado)",
            )
        pomodoro.status = Pomodoro.Status.COMPLETED
        pomodoro.completed_at = now

    pomodoro.save()

    payload = {"data": _pomodoro_resource(pomodoro)}
    if action == 'complete':
        consecutive = _consecutive_completed_count(session)
        payload["meta"] = {
            "suggested_break_minutes": 15 if consecutive % 4 == 0 else 5,
            "consecutive_completed": consecutive,
        }

    return payload, 200
