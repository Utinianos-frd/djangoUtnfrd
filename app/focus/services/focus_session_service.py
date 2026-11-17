from datetime import datetime
from typing import Any, cast

from django.utils import timezone
from rest_framework.request import Request
from app.users.models import Users
from app.organizations.models import Organization
from app.tasks.models import Task, TaskDependency
from app.tasks.services.task_service import _is_blocked
from ..models import FocusSession, Pomodoro
from ..serializers.create_session_serializer import CreateFocusSessionSerializer
from .common import error, extract_attributes, serializer_errors


def _ordered_tasks(session: FocusSession) -> list[Task]:
    """Tareas en el orden en que se eligieron: las filas de la tabla intermedia se insertan en ese orden
    (ver iniciar_sesion), así que su id lo preserva. session.tasks.all() no garantiza ningún orden."""
    rows = (
        FocusSession.tasks.through.objects.filter(focussession=session)
        .select_related('task__project__group').order_by('id')
    )
    return [row.task for row in rows]


def _task_summary(task: Task) -> dict[str, Any]:
    """Datos de la tarea para que el front no dependa de localStorage: título, estado actual y su ruta."""
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "blocked": _is_blocked(task),
        "org_id": task.project.group.organization_id,
        "group_id": task.project.group_id,
        "project_id": task.project_id,
    }


def _current_pomodoro(session: FocusSession) -> dict[str, Any] | None:
    """Pomodoro running/paused de la sesión (a lo sumo uno), para restaurar el timer al recargar."""
    pomodoro = session.pomodoros.filter(status__in=[Pomodoro.Status.RUNNING, Pomodoro.Status.PAUSED]).first()
    if not pomodoro:
        return None
    return {
        "id": pomodoro.id,
        "task_id": pomodoro.task_id,
        "status": pomodoro.status,
        "duration_minutes": Pomodoro.DURATION_MINUTES,
        "started_at": pomodoro.started_at.isoformat(),
        "remaining_seconds": pomodoro.remaining_seconds(),
    }


def close_pomodoro(pomodoro: Pomodoro, status: str, now: datetime) -> None:
    """Cierra un pomodoro en curso (completed/cancelled/interrupted). Si estaba pausado, esa última pausa
    se suma a total_paused_seconds para que focus_seconds() no la cuente como foco. No guarda."""
    if pomodoro.status == Pomodoro.Status.PAUSED and pomodoro.paused_at:
        pomodoro.total_paused_seconds += int((now - pomodoro.paused_at).total_seconds())
        pomodoro.paused_at = None
    pomodoro.status = status
    pomodoro.ended_at = now
    if status == Pomodoro.Status.COMPLETED:
        pomodoro.completed_at = now


def _session_resource(session: FocusSession) -> dict[str, Any]:
    """Recurso JSON:API de una FocusSession."""
    tasks = _ordered_tasks(session)
    return {
        "type": "focus_sessions",
        "id": str(session.id),
        "attributes": {
            "goal_text": session.goal_text,
            "status": session.status,
            "task_ids": [task.id for task in tasks],
            "tasks": [_task_summary(task) for task in tasks],
            "current_pomodoro": _current_pomodoro(session),
            "started_at": session.started_at.isoformat(),
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        },
    }


def get_own_session(user: Users, session_id: int) -> FocusSession | None:
    """Una sesión le pertenece solo a su user — no hay rol de organización que dé acceso a la ajena."""
    return FocusSession.objects.filter(id=session_id, user=user).first()


def iniciar_sesion(request: Request) -> tuple[dict[str, Any], int]:
    """Crea la sesión si cada tarea está asignada al usuario y su organización es plan Pro (RF-44/8.4)."""
    user = cast(Users, request.user)
    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = CreateFocusSessionSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    if FocusSession.objects.filter(user=user, status=FocusSession.Status.ACTIVE).exists():
        return error(409, "Ya tenés una sesión de modo foco activa")

    task_ids = list(dict.fromkeys(serializer.validated_data['task_ids']))  # sin duplicados, en el orden recibido
    tasks_by_id = Task.objects.select_related('project__group__organization').in_bulk(task_ids)
    if len(tasks_by_id) != len(task_ids):
        return error(400, "Alguna de las tareas indicadas no existe")
    tasks = [tasks_by_id[task_id] for task_id in task_ids]

    for task in tasks:
        if not task.assignees.filter(id=user.id).exists():
            return error(403, f"La tarea '{task.title}' no te fue asignada")
        organization = task.project.group.organization
        if organization.plan != Organization.Plan.PRO:
            return error(
                403,
                f"Modo Foco requiere plan Pro. La organización '{organization.name}' está en plan Free.",
            )
        if task.status == Task.Status.DONE:
            return error(400, f"La tarea '{task.title}' ya está completada")
        blocker = TaskDependency.objects.filter(
            blocked_task=task, dependency_type=TaskDependency.Type.FINISH_TO_START,
        ).exclude(blocking_task__status=Task.Status.DONE).select_related('blocking_task').order_by('id').first()
        if blocker:
            return error(400, f"La tarea '{task.title}' está bloqueada por '{blocker.blocking_task.title}'")

    session = FocusSession.objects.create(user=user, goal_text=serializer.validated_data['goal_text'])
    # bulk_create en vez de tasks.set(): set() pasa por un set y pierde el orden (ver _ordered_tasks).
    FocusSession.tasks.through.objects.bulk_create(
        [FocusSession.tasks.through(focussession=session, task=task) for task in tasks]
    )

    return {"data": _session_resource(session)}, 201


def obtener_sesion_activa(request: Request) -> tuple[dict[str, Any], int]:
    """Sesión activa del usuario, o {"data": null} si no tiene (JSON:API: recurso vacío, no un 404).
    El frontend la consulta en cada carga, así que "no hay sesión" es un caso normal, no un error."""
    session = FocusSession.objects.filter(user=cast(Users, request.user), status=FocusSession.Status.ACTIVE).first()
    if not session:
        return {"data": None}, 200
    return {"data": _session_resource(session)}, 200


def finalizar_sesion(request: Request, session_id: int) -> tuple[dict[str, Any], int]:
    """Cierra la sesión (el pomodoro en curso queda 'interrupted') y arma el resumen: tiempo, pomodoros, tareas (RF-53)."""
    session = get_own_session(cast(Users, request.user), session_id)
    if not session:
        return error(404, "Sesión no encontrada")

    if session.status != FocusSession.Status.ACTIVE:
        return error(409, "Esta sesión ya terminó")

    now = timezone.now()
    for in_progress in session.pomodoros.filter(status__in=[Pomodoro.Status.RUNNING, Pomodoro.Status.PAUSED]):
        close_pomodoro(in_progress, Pomodoro.Status.INTERRUPTED, now)
        in_progress.save()

    session.status = FocusSession.Status.ENDED
    session.ended_at = now
    session.save()

    completed_pomodoros = session.pomodoros.filter(status=Pomodoro.Status.COMPLETED)
    # El foco de los cancelados e interrumpidos también es tiempo trabajado; solo no cuentan como pomodoro completado.
    worked_seconds = sum(
        p.focus_seconds()
        for p in session.pomodoros.filter(status__in=[
            Pomodoro.Status.COMPLETED, Pomodoro.Status.CANCELLED, Pomodoro.Status.INTERRUPTED,
        ])
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
