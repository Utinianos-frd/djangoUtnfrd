from datetime import timedelta

import pytest
from django.utils import timezone

from app.focus.models import FocusSession, Pomodoro
from app.focus.views.pomodoro_view import pomodoros, pomodoro_detail
from app.tasks.models import Task

pytestmark = pytest.mark.django_db


def _start_payload(task_id):
    return {"data": {"type": "pomodoros", "attributes": {"task_id": task_id}}}


def _action_payload(action):
    return {"data": {"type": "pomodoros", "attributes": {"action": action}}}


@pytest.fixture
def act(call, focus_user, active_session):
    """Aplica una acción (pause/resume/cancel/complete) a un pomodoro de active_session como su dueño."""

    def _act(pomodoro, action, user=None):
        return call(
            pomodoro_detail, 'patch', '/', user or focus_user.user, _action_payload(action),
            session_id=active_session.id, pomodoro_id=pomodoro.id,
        )

    return _act


@pytest.fixture
def make_pomodoro(focus_user, active_session):
    def _make_pomodoro(status=Pomodoro.Status.RUNNING, task=None):
        return Pomodoro.objects.create(session=active_session, task=task or focus_user.task_a, status=status)

    return _make_pomodoro


class TestIniciarPomodoro:

    def test_inicia_pomodoro_de_25_minutos(self, call, focus_user, active_session):
        status, data = call(
            pomodoros, 'post', '/', focus_user.user, _start_payload(focus_user.task_a.id), session_id=active_session.id,
        )

        assert status == 201
        attributes = data['data']['attributes']
        assert attributes['status'] == 'running'
        assert attributes['duration_minutes'] == 25
        assert attributes['task_id'] == focus_user.task_a.id

    @pytest.mark.parametrize('status', [Pomodoro.Status.RUNNING, Pomodoro.Status.PAUSED])
    def test_solo_un_pomodoro_en_curso_por_sesion(self, call, focus_user, active_session, make_pomodoro, status):
        make_pomodoro(status=status)

        response_status, _data = call(
            pomodoros, 'post', '/', focus_user.user, _start_payload(focus_user.task_b.id), session_id=active_session.id,
        )

        assert response_status == 409

    def test_puede_iniciar_otro_despues_de_completar(self, call, focus_user, active_session, make_pomodoro):
        make_pomodoro(status=Pomodoro.Status.COMPLETED)

        status, _data = call(
            pomodoros, 'post', '/', focus_user.user, _start_payload(focus_user.task_b.id), session_id=active_session.id,
        )

        assert status == 201

    def test_tarea_fuera_de_la_sesion_da_400(self, call, focus_user, active_session):
        outside = Task.objects.create(project=focus_user.project, title='Fuera')
        outside.assignees.set([focus_user.user])

        status, _data = call(
            pomodoros, 'post', '/', focus_user.user, _start_payload(outside.id), session_id=active_session.id,
        )

        assert status == 400

    def test_sesion_terminada_da_409(self, call, focus_user, active_session):
        active_session.status = FocusSession.Status.ENDED
        active_session.save()

        status, _data = call(
            pomodoros, 'post', '/', focus_user.user, _start_payload(focus_user.task_a.id), session_id=active_session.id,
        )

        assert status == 409

    def test_sesion_ajena_da_404(self, call, focus_user, active_session):
        status, _data = call(
            pomodoros, 'post', '/', focus_user.other, _start_payload(focus_user.task_a.id), session_id=active_session.id,
        )

        assert status == 404
        assert not Pomodoro.objects.exists()


class TestMaquinaDeEstados:
    """Transiciones válidas: running -> paused -> running -> completed; cancel desde running o paused."""

    def test_pausar_un_pomodoro_corriendo(self, act, make_pomodoro):
        pomodoro = make_pomodoro()

        status, data = act(pomodoro, 'pause')

        assert status == 200
        assert data['data']['attributes']['status'] == 'paused'
        pomodoro.refresh_from_db()
        assert pomodoro.paused_at is not None

    def test_reanudar_acumula_el_tiempo_pausado(self, act, make_pomodoro):
        pomodoro = make_pomodoro(status=Pomodoro.Status.PAUSED)
        Pomodoro.objects.filter(id=pomodoro.id).update(
            paused_at=timezone.now() - timedelta(seconds=90), total_paused_seconds=30,
        )

        status, data = act(pomodoro, 'resume')

        assert status == 200
        assert data['data']['attributes']['status'] == 'running'
        pomodoro.refresh_from_db()
        assert pomodoro.paused_at is None
        assert 120 <= pomodoro.total_paused_seconds <= 121  # 30 previos + ~90 de esta pausa

    def test_completar_un_pomodoro_corriendo(self, act, make_pomodoro):
        pomodoro = make_pomodoro()

        status, data = act(pomodoro, 'complete')

        assert status == 200
        assert data['data']['attributes']['status'] == 'completed'
        assert data['data']['attributes']['completed_at'] is not None

    @pytest.mark.parametrize('status', [Pomodoro.Status.RUNNING, Pomodoro.Status.PAUSED])
    def test_cancelar_desde_running_o_paused(self, act, make_pomodoro, status):
        pomodoro = make_pomodoro(status=status)

        response_status, data = act(pomodoro, 'cancel')

        assert response_status == 200
        assert data['data']['attributes']['status'] == 'cancelled'

    @pytest.mark.parametrize('status, action', [
        (Pomodoro.Status.PAUSED, 'pause'),
        (Pomodoro.Status.RUNNING, 'resume'),
        (Pomodoro.Status.PAUSED, 'complete'),  # hay que reanudar antes de completar
        (Pomodoro.Status.COMPLETED, 'pause'),
        (Pomodoro.Status.COMPLETED, 'resume'),
        (Pomodoro.Status.COMPLETED, 'complete'),
        (Pomodoro.Status.COMPLETED, 'cancel'),
        (Pomodoro.Status.CANCELLED, 'pause'),
        (Pomodoro.Status.CANCELLED, 'resume'),
        (Pomodoro.Status.CANCELLED, 'complete'),
        (Pomodoro.Status.CANCELLED, 'cancel'),
    ])
    def test_transiciones_invalidas_dan_409_sin_cambiar_estado(self, act, make_pomodoro, status, action):
        pomodoro = make_pomodoro(status=status)

        response_status, _data = act(pomodoro, action)

        assert response_status == 409
        pomodoro.refresh_from_db()
        assert pomodoro.status == status

    def test_accion_invalida_da_400(self, act, make_pomodoro):
        status, _data = act(make_pomodoro(), 'reiniciar')

        assert status == 400

    def test_pomodoro_de_sesion_ajena_da_404(self, act, make_pomodoro, focus_user):
        pomodoro = make_pomodoro()

        status, _data = act(pomodoro, 'pause', user=focus_user.other)

        assert status == 404
        pomodoro.refresh_from_db()
        assert pomodoro.status == Pomodoro.Status.RUNNING


class TestDescansoSugerido:
    """RF-50: descanso corto (5) tras cada pomodoro, largo (15) cada 4 completados seguidos."""

    def _complete_previous(self, make_pomodoro, statuses):
        """Pomodoros ya terminados, con started_at escalonado hacia el pasado para que el orden sea determinístico."""
        now = timezone.now()
        for minutes_ago, status in zip(range(len(statuses) * 30, 0, -30), statuses):
            pomodoro = make_pomodoro(status=status)
            Pomodoro.objects.filter(id=pomodoro.id).update(started_at=now - timedelta(minutes=minutes_ago))

    def test_primer_pomodoro_sugiere_descanso_corto(self, act, make_pomodoro):
        status, data = act(make_pomodoro(), 'complete')

        assert status == 200
        assert data['meta'] == {'suggested_break_minutes': 5, 'consecutive_completed': 1}

    def test_cuarto_seguido_sugiere_descanso_largo(self, act, make_pomodoro):
        self._complete_previous(make_pomodoro, [Pomodoro.Status.COMPLETED] * 3)

        _status, data = act(make_pomodoro(), 'complete')

        assert data['meta'] == {'suggested_break_minutes': 15, 'consecutive_completed': 4}

    def test_un_cancelado_corta_la_racha(self, act, make_pomodoro):
        self._complete_previous(
            make_pomodoro,
            [Pomodoro.Status.COMPLETED, Pomodoro.Status.COMPLETED, Pomodoro.Status.CANCELLED, Pomodoro.Status.COMPLETED],
        )

        _status, data = act(make_pomodoro(), 'complete')

        assert data['meta'] == {'suggested_break_minutes': 5, 'consecutive_completed': 2}

    def test_otras_acciones_no_devuelven_meta(self, act, make_pomodoro):
        _status, data = act(make_pomodoro(), 'pause')

        assert 'meta' not in data
