from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from app.focus.models import FocusSession, Pomodoro
from app.focus.views.focus_session_view import focus_sessions, active_focus_session, end_focus_session
from app.organizations.models import Organization
from app.tasks.models import Task, TaskDependency

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


class TestValidacionesAlIniciarSesion:

    def test_tarea_done_da_400(self, call, focus_user):
        focus_user.task_b.status = Task.Status.DONE
        focus_user.task_b.save()

        status, data = call(
            focus_sessions, 'post', '/', focus_user.user,
            _session_payload(goal_text='x', task_ids=[focus_user.task_a.id, focus_user.task_b.id]),
        )

        assert status == 400
        assert data['errors'][0]['detail'] == "La tarea 'Tarea B' ya está completada"
        assert not FocusSession.objects.exists()

    def test_tarea_bloqueada_por_fs_da_400(self, call, focus_user):
        blocker = Task.objects.create(project=focus_user.project, title='Diseño')
        TaskDependency.objects.create(
            blocking_task=blocker, blocked_task=focus_user.task_a, dependency_type=TaskDependency.Type.FINISH_TO_START,
        )

        status, data = call(
            focus_sessions, 'post', '/', focus_user.user, _session_payload(goal_text='x', task_ids=[focus_user.task_a.id]),
        )

        assert status == 400
        assert data['errors'][0]['detail'] == "La tarea 'Tarea A' está bloqueada por 'Diseño'"

    @pytest.mark.parametrize('blocker_status, dependency_type', [
        (Task.Status.DONE, TaskDependency.Type.FINISH_TO_START),  # la bloqueante ya terminó
        (Task.Status.PENDING, TaskDependency.Type.FINISH_TO_FINISH),  # FF no impide arrancar
    ])
    def test_dependencias_que_no_bloquean_se_aceptan(self, call, focus_user, blocker_status, dependency_type):
        blocker = Task.objects.create(project=focus_user.project, title='Diseño', status=blocker_status)
        TaskDependency.objects.create(blocking_task=blocker, blocked_task=focus_user.task_a, dependency_type=dependency_type)

        status, _data = call(
            focus_sessions, 'post', '/', focus_user.user, _session_payload(goal_text='x', task_ids=[focus_user.task_a.id]),
        )

        assert status == 201

    def test_respeta_el_orden_y_saca_duplicados(self, call, focus_user):
        task_c = Task.objects.create(project=focus_user.project, title='Tarea C')
        task_c.assignees.set([focus_user.user])
        ids = [task_c.id, focus_user.task_a.id, task_c.id, focus_user.task_b.id, focus_user.task_a.id]

        status, data = call(focus_sessions, 'post', '/', focus_user.user, _session_payload(goal_text='x', task_ids=ids))
        _s, active = call(active_focus_session, 'get', '/', focus_user.user)

        expected = [task_c.id, focus_user.task_a.id, focus_user.task_b.id]
        assert status == 201
        assert data['data']['attributes']['task_ids'] == expected
        assert active['data']['attributes']['task_ids'] == expected
        assert [t['id'] for t in active['data']['attributes']['tasks']] == expected

    def test_goal_text_de_mas_de_200_caracteres_da_400(self, call, focus_user):
        status, data = call(
            focus_sessions, 'post', '/', focus_user.user,
            _session_payload(goal_text='x' * 201, task_ids=[focus_user.task_a.id]),
        )

        assert status == 400
        assert data['errors'][0]['source']['pointer'] == '/data/attributes/goal_text'
        assert data['errors'][0]['detail'] == 'Asegúrese de que este campo no tenga más de 200 caracteres.'

    def test_goal_text_de_200_caracteres_se_acepta(self, call, focus_user):
        status, _data = call(
            focus_sessions, 'post', '/', focus_user.user,
            _session_payload(goal_text='x' * 200, task_ids=[focus_user.task_a.id]),
        )

        assert status == 201


class TestDatosDeLaSesion:

    def test_incluye_las_tareas_con_su_ruta_y_estado_actual(self, call, focus_user, active_session):
        focus_user.task_b.status = Task.Status.DONE  # completada desde el tablero, después de armar la sesión
        focus_user.task_b.save()
        project = focus_user.project

        _status, data = call(active_focus_session, 'get', '/', focus_user.user)

        route = {'org_id': project.group.organization_id, 'group_id': project.group_id, 'project_id': project.id}
        assert data['data']['attributes']['tasks'] == [
            {'id': focus_user.task_a.id, 'title': 'Tarea A', 'status': 'pending', 'blocked': False, **route},
            {'id': focus_user.task_b.id, 'title': 'Tarea B', 'status': 'done', 'blocked': False, **route},
        ]

    def test_tarea_bloqueada_se_marca_blocked(self, call, focus_user, active_session):
        blocker = Task.objects.create(project=focus_user.project, title='Diseño')
        TaskDependency.objects.create(
            blocking_task=blocker, blocked_task=focus_user.task_a, dependency_type=TaskDependency.Type.FINISH_TO_START,
        )

        _status, data = call(active_focus_session, 'get', '/', focus_user.user)

        assert data['data']['attributes']['tasks'][0]['blocked'] is True

    def test_sin_pomodoro_en_curso_current_pomodoro_es_null(self, call, focus_user, active_session):
        Pomodoro.objects.create(session=active_session, task=focus_user.task_a, status=Pomodoro.Status.COMPLETED)

        _status, data = call(active_focus_session, 'get', '/', focus_user.user)

        assert data['data']['attributes']['current_pomodoro'] is None

    def test_al_crear_la_sesion_current_pomodoro_es_null(self, call, focus_user):
        _status, data = call(
            focus_sessions, 'post', '/', focus_user.user, _session_payload(goal_text='x', task_ids=[focus_user.task_a.id]),
        )

        assert data['data']['attributes']['current_pomodoro'] is None

    def test_pomodoro_corriendo_se_puede_restaurar(self, call, focus_user, active_session):
        pomodoro = Pomodoro.objects.create(session=active_session, task=focus_user.task_b)
        Pomodoro.objects.filter(id=pomodoro.id).update(
            started_at=timezone.now() - timedelta(minutes=10), total_paused_seconds=60,
        )
        pomodoro.refresh_from_db()

        _status, data = call(active_focus_session, 'get', '/', focus_user.user)

        current = data['data']['attributes']['current_pomodoro']
        remaining = current.pop('remaining_seconds')
        assert current == {
            'id': pomodoro.id, 'task_id': focus_user.task_b.id, 'status': 'running',
            'duration_minutes': 25, 'started_at': pomodoro.started_at.isoformat(),
        }
        assert 16 * 60 - 2 <= remaining <= 16 * 60  # 25 - (10 - 1 de pausa)

    def test_pomodoro_pausado_no_sigue_descontando(self, call, focus_user, active_session):
        now = timezone.now()
        pomodoro = Pomodoro.objects.create(session=active_session, task=focus_user.task_a)
        Pomodoro.objects.filter(id=pomodoro.id).update(
            status=Pomodoro.Status.PAUSED, started_at=now - timedelta(minutes=30), paused_at=now - timedelta(minutes=25),
        )  # 5 min de foco antes de pausar

        _status, data = call(active_focus_session, 'get', '/', focus_user.user)

        current = data['data']['attributes']['current_pomodoro']
        assert current['status'] == 'paused'
        assert current['remaining_seconds'] == 20 * 60


class TestSesionActiva:

    def test_devuelve_la_sesion_activa(self, call, focus_user, active_session):
        status, data = call(active_focus_session, 'get', '/', focus_user.user)

        assert status == 200
        assert data['data']['id'] == str(active_session.id)

    def test_sin_sesion_activa_da_200_con_data_null(self, call, focus_user, active_session):
        status, data = call(active_focus_session, 'get', '/', focus_user.other)

        assert status == 200
        assert data == {"data": None}

    def test_sesion_terminada_no_cuenta_como_activa(self, call, focus_user, active_session):
        active_session.status = FocusSession.Status.ENDED
        active_session.save()

        status, data = call(active_focus_session, 'get', '/', focus_user.user)

        assert status == 200
        assert data['data'] is None


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

    @pytest.mark.parametrize('status', [Pomodoro.Status.RUNNING, Pomodoro.Status.PAUSED])
    def test_el_pomodoro_en_curso_queda_interrumpido(self, call, focus_user, active_session, status):
        pomodoro = Pomodoro.objects.create(session=active_session, task=focus_user.task_a, status=status)

        call(end_focus_session, 'post', '/', focus_user.user, session_id=active_session.id)

        pomodoro.refresh_from_db()
        assert pomodoro.status == Pomodoro.Status.INTERRUPTED
        assert pomodoro.ended_at is not None
        assert pomodoro.paused_at is None

    def test_interrumpido_y_cancelado_suman_foco_pero_no_cuentan_como_completados(
        self, call, focus_user, active_session,
    ):
        self._completed_pomodoro(active_session, focus_user.task_a, worked_minutes=25)
        now = timezone.now()
        cancelled = Pomodoro.objects.create(session=active_session, task=focus_user.task_a)
        Pomodoro.objects.filter(id=cancelled.id).update(
            status=Pomodoro.Status.CANCELLED, started_at=now - timedelta(minutes=12),
            ended_at=now - timedelta(minutes=2), total_paused_seconds=60,
        )  # 10 min - 1 de pausa = 9 min de foco
        running = Pomodoro.objects.create(session=active_session, task=focus_user.task_b)
        Pomodoro.objects.filter(id=running.id).update(started_at=now - timedelta(minutes=7))  # 7 min de foco

        status, data = call(end_focus_session, 'post', '/', focus_user.user, session_id=active_session.id)

        assert status == 200
        summary = data['data']['attributes']
        assert (25 + 9 + 7) * 60 <= summary['worked_seconds'] <= (25 + 9 + 7) * 60 + 2
        assert summary['pomodoros_completed'] == 1

    def test_un_pausado_interrumpido_no_suma_su_pausa(self, call, focus_user, active_session):
        now = timezone.now()
        paused = Pomodoro.objects.create(session=active_session, task=focus_user.task_a)
        Pomodoro.objects.filter(id=paused.id).update(
            status=Pomodoro.Status.PAUSED, started_at=now - timedelta(minutes=20), paused_at=now - timedelta(minutes=15),
        )  # 5 min de foco y 15 en pausa

        _status, data = call(end_focus_session, 'post', '/', focus_user.user, session_id=active_session.id)

        assert 5 * 60 <= data['data']['attributes']['worked_seconds'] <= 5 * 60 + 2

    def test_no_se_puede_terminar_dos_veces(self, call, focus_user, active_session):
        call(end_focus_session, 'post', '/', focus_user.user, session_id=active_session.id)

        status, _data = call(end_focus_session, 'post', '/', focus_user.user, session_id=active_session.id)

        assert status == 409

    def test_sesion_ajena_da_404(self, call, focus_user, active_session):
        status, _data = call(end_focus_session, 'post', '/', focus_user.other, session_id=active_session.id)

        assert status == 404
        active_session.refresh_from_db()
        assert active_session.status == FocusSession.Status.ACTIVE
