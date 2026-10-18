from django.utils import timezone
from app.organizations.models import Organization
from app.tasks.models import Task
from ..models import FocusSession, Pomodoro
from ..serializers.create_session_serializer import CreateFocusSessionSerializer
from .common import error, extract_attributes, serializer_errors


def _session_resource(session):
    return {
        "type": "focus_sessions",
        "id": str(session.id),
        "attributes": {
            "goal_text": session.goal_text,
            "status": session.status,
            "task_ids": list(session.tasks.values_list('id', flat=True)),
            "started_at": session.started_at.isoformat(),
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        },
    }


def get_own_session(user, session_id):
    return FocusSession.objects.filter(id=session_id, user=user).first()


def iniciar_sesion(request):
    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = CreateFocusSessionSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    if FocusSession.objects.filter(user=request.user, status=FocusSession.Status.ACTIVE).exists():
        return error(409, "Ya tenés una sesión de modo foco activa")

    task_ids = serializer.validated_data['task_ids']
    tasks = list(
        Task.objects.filter(id__in=task_ids).select_related('project__group__organization')
    )
    if len(tasks) != len(set(task_ids)):
        return error(400, "Alguna de las tareas indicadas no existe")

    for task in tasks:
        if not task.assignees.filter(id=request.user.id).exists():
            return error(403, f"La tarea '{task.title}' no te fue asignada")
        organization = task.project.group.organization
        if organization.plan != Organization.Plan.PRO:
            return error(
                403,
                f"Modo Foco requiere plan Pro. La organización '{organization.name}' está en plan Free.",
            )

    session = FocusSession.objects.create(user=request.user, goal_text=serializer.validated_data['goal_text'])
    session.tasks.set(tasks)

    return {"data": _session_resource(session)}, 201


def obtener_sesion_activa(request):
    session = FocusSession.objects.filter(user=request.user, status=FocusSession.Status.ACTIVE).first()
    if not session:
        return error(404, "No tenés una sesión de modo foco activa")
    return {"data": _session_resource(session)}, 200


def finalizar_sesion(request, session_id):
    session = get_own_session(request.user, session_id)
    if not session:
        return error(404, "Sesión no encontrada")

    if session.status != FocusSession.Status.ACTIVE:
        return error(409, "Esta sesión ya terminó")

    Pomodoro.objects.filter(
        session=session, status__in=[Pomodoro.Status.RUNNING, Pomodoro.Status.PAUSED],
    ).update(status=Pomodoro.Status.CANCELLED)

    session.status = FocusSession.Status.ENDED
    session.ended_at = timezone.now()
    session.save()

    completed_pomodoros = session.pomodoros.filter(status=Pomodoro.Status.COMPLETED)
    worked_seconds = sum(
        max(int((p.completed_at - p.started_at).total_seconds()) - p.total_paused_seconds, 0)
        for p in completed_pomodoros
    )
    completed_tasks = session.tasks.filter(status=Task.Status.DONE)

    return {
        "data": {
            "type": "focus_session_summary",
            "id": str(session.id),
            "attributes": {
                "worked_seconds": worked_seconds,
                "pomodoros_completed": completed_pomodoros.count(),
                "tasks_completed_count": completed_tasks.count(),
                "tasks_completed_titles": list(completed_tasks.values_list('title', flat=True)),
            },
        }
    }, 200
