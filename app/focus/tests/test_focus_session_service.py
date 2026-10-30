from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from app.focus.models import FocusSession, Pomodoro
from app.focus.views.focus_session_view import focus_sessions, active_focus_session, end_focus_session
from app.organizations.models import Organization
from app.tasks.models import Task

pytestmark = pytest.mark.django_db


def _session_payload(**attrs):
    return {"data": {"type": "focus_sessions", "attributes": attrs}}


class TestIniciarSesion:

    def test_inicia_sesion_con_tareas_asignadas_en_plan_pro(self, call, focus_user):
        status, data = call(
            focus_sessions, 'post', '/', focus_user.user,
            _session_payload(goal_text='Terminar el login', task_ids=[focus_user.task_a.id, focus_user.task_b.id]),
        )

        assert status == 201
        attributes = data['data']['attributes']
        assert attributes['status'] == 'active'
        assert sorted(attributes['task_ids']) == sorted([focus_user.task_a.id, focus_user.task_b.id])
        assert attributes['ended_at'] is None

    def test_plan_free_da_403(self, call, focus_user, make_project):
        free_task = Task.objects.create(project=make_project(plan=Organization.Plan.FREE, org_name='Free Org'), title='Free')
        free_task.assignees.set([focus_user.user])

        status, data = call(
            focus_sessions, 'post', '/', focus_user.user,
            _session_payload(goal_text='x', task_ids=[focus_user.task_a.id, free_task.id]),
        )

        assert status == 403
        assert 'Free Org' in data['errors'][0]['detail']
        assert not FocusSession.objects.exists()

    def test_tarea_no_asignada_da_403(self, call, focus_user):
        focus_user.task_b.assignees.clear()

        status, _data = call(
            focus_sessions, 'post', '/', focus_user.user,
            _session_payload(goal_text='x', task_ids=[focus_user.task_b.id]),
        )

        assert status == 403

    def test_tarea_inexistente_da_400(self, call, focus_user):
        status, _data = call(
            focus_sessions, 'post', '/', focus_user.user, _session_payload(goal_text='x', task_ids=[999]),
        )

        assert status == 400

    def test_lista_de_tareas_vacia_da_400(self, call, focus_user):
        status, data = call(focus_sessions, 'post', '/', focus_user.user, _session_payload(goal_text='x', task_ids=[]))

        assert status == 400
        assert data['errors'][0]['source']['pointer'] == '/data/attributes/task_ids'

    def test_ids_repetidos_no_rompen_la_validacion(self, call, focus_user):
        status, data = call(
            focus_sessions, 'post', '/', focus_user.user,
            _session_payload(goal_text='x', task_ids=[focus_user.task_a.id, focus_user.task_a.id]),
        )

        assert status == 201
        assert data['data']['attributes']['task_ids'] == [focus_user.task_a.id]

    def test_no_puede_haber_dos_sesiones_activas(self, call, focus_user, active_session):
        status, _data = call(
            focus_sessions, 'post', '/', focus_user.user, _session_payload(goal_text='x', task_ids=[focus_user.task_a.id]),
        )

        assert status == 409

    def test_con_la_sesion_anterior_terminada_puede_iniciar_otra(self, call, focus_user, active_session):
        active_session.status = FocusSession.Status.ENDED
        active_session.save()

        status, _data = call(
            focus_sessions, 'post', '/', focus_user.user, _session_payload(goal_text='x', task_ids=[focus_user.task_a.id]),
        )

        assert status == 201

    def test_constraint_de_db_impide_dos_activas(self, focus_user, active_session):
        with pytest.raises(IntegrityError), transaction.atomic():
            FocusSession.objects.create(user=focus_user.user, goal_text='otra')


class TestSesionActiva:

    def test_devuelve_la_sesion_activa(self, call, focus_user, active_session):
        status, data = call(active_focus_session, 'get', '/', focus_user.user)

        assert status == 200
        assert data['data']['id'] == str(active_session.id)

    def test_sin_sesion_activa_da_404(self, call, focus_user, active_session):
        status, _data = call(active_focus_session, 'get', '/', focus_user.other)

        assert status == 404


class TestFinalizarSesion:

    def _completed_pomodoro(self, session, task, worked_minutes, paused_seconds=0):
        """Pomodoro ya completado con tiempos controlados (started_at es auto_now_add, así que se pisa con update)."""
        pomodoro = Pomodoro.objects.create(session=session, task=task)
        end = timezone.now()
        Pomodoro.objects.filter(id=pomodoro.id).update(
            status=Pomodoro.Status.COMPLETED,
            started_at=end - timedelta(minutes=worked_minutes, seconds=paused_seconds),
            completed_at=end,
            total_paused_seconds=paused_seconds,
        )

    def test_resumen_con_tiempo_trabajado_pomodoros_y_tareas(self, call, focus_user, active_session):
        self._completed_pomodoro(active_session, focus_user.task_a, worked_minutes=25, paused_seconds=120)
        self._completed_pomodoro(active_session, focus_user.task_b, worked_minutes=25)
        Pomodoro.objects.create(session=active_session, task=focus_user.task_a, status=Pomodoro.Status.CANCELLED)
        focus_user.task_a.status = Task.Status.DONE
        focus_user.task_a.save()

        status, data = call(end_focus_session, 'post', '/', focus_user.user, session_id=active_session.id)

        assert status == 200
        summary = data['data']['attributes']
        assert summary['worked_seconds'] == 50 * 60  # las pausas no cuentan como tiempo trabajado
        assert summary['pomodoros_completed'] == 2
        assert summary['tasks_completed_count'] == 1
        assert summary['tasks_completed_titles'] == ['Tarea A']
        active_session.refresh_from_db()
        assert active_session.status == FocusSession.Status.ENDED
        assert active_session.ended_at is not None

    def test_cancela_los_pomodoros_en_curso(self, call, focus_user, active_session):
        running = Pomodoro.objects.create(session=active_session, task=focus_user.task_a)
        paused = Pomodoro.objects.create(session=active_session, task=focus_user.task_b, status=Pomodoro.Status.PAUSED)

        call(end_focus_session, 'post', '/', focus_user.user, session_id=active_session.id)

        running.refresh_from_db()
        paused.refresh_from_db()
        assert running.status == Pomodoro.Status.CANCELLED
        assert paused.status == Pomodoro.Status.CANCELLED

    def test_no_se_puede_terminar_dos_veces(self, call, focus_user, active_session):
        call(end_focus_session, 'post', '/', focus_user.user, session_id=active_session.id)

        status, _data = call(end_focus_session, 'post', '/', focus_user.user, session_id=active_session.id)

        assert status == 409

    def test_sesion_ajena_da_404(self, call, focus_user, active_session):
        status, _data = call(end_focus_session, 'post', '/', focus_user.other, session_id=active_session.id)

        assert status == 404
        active_session.refresh_from_db()
        assert active_session.status == FocusSession.Status.ACTIVE
