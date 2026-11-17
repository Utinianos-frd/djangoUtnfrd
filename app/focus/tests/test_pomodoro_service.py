from datetime import timedelta

import pytest
from django.utils import timezone

from app.focus.models import FocusSession, Pomodoro
from app.focus.views.pomodoro_view import pomodoros, pomodoro_detail
from app.tasks.models import Task, TaskDependency

pytestmark = pytest.mark.django_db


def _start_payload(task_id):
    return {"data": {"type": "pomodoros", "attributes": {"task_id": task_id}}}


def _action_payload(action):
    return {"data": {"type": "pomodoros", "attributes": {"action": action}}}


def _switch_payload(task_id):
    attrs = {"action": "switch_task"}
    if task_id is not None:
        attrs["task_id"] = task_id
    return {"data": {"type": "pomodoros", "attributes": attrs}}


@pytest.fixture
def act(call, focus_user, active_session):
    """Aplica una acción (pause/resume/cancel/complete) a un pomodoro de active_session como su dueño."""

    def _act(pomodoro, action, user=None):
        return call(
            pomodoro_detail, 'patch', '/', user or focus_user.user, _action_payload(action),
            session_id=active_session.id, pomodoro_id=pomodoro.id,
        )

    return _act


FULL = Pomodoro.DURATION_MINUTES * 60


@pytest.fixture
def make_pomodoro(focus_user, active_session):
    """elapsed_seconds: hace cuánto arrancó (started_at es auto_now_add, así que se pisa con update)."""

    def _make_pomodoro(status=Pomodoro.Status.RUNNING, task=None, elapsed_seconds=0, paused_seconds=0):
        pomodoro = Pomodoro.objects.create(session=active_session, task=task or focus_user.task_a, status=status)
        if elapsed_seconds or paused_seconds:
            Pomodoro.objects.filter(id=pomodoro.id).update(
                started_at=timezone.now() - timedelta(seconds=elapsed_seconds),
                total_paused_seconds=paused_seconds,
            )
            pomodoro.refresh_from_db()
        return pomodoro

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
        pomodoro = make_pomodoro(elapsed_seconds=FULL)

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
        status, data = act(make_pomodoro(elapsed_seconds=FULL), 'complete')

        assert status == 200
        assert data['meta'] == {'suggested_break_minutes': 5, 'consecutive_completed': 1}

    def test_cuarto_seguido_sugiere_descanso_largo(self, act, make_pomodoro):
        self._complete_previous(make_pomodoro, [Pomodoro.Status.COMPLETED] * 3)

        _status, data = act(make_pomodoro(elapsed_seconds=FULL), 'complete')

        assert data['meta'] == {'suggested_break_minutes': 15, 'consecutive_completed': 4}

    def test_un_cancelado_corta_la_racha(self, act, make_pomodoro):
        self._complete_previous(
            make_pomodoro,
            [Pomodoro.Status.COMPLETED, Pomodoro.Status.COMPLETED, Pomodoro.Status.CANCELLED, Pomodoro.Status.COMPLETED],
        )

        _status, data = act(make_pomodoro(elapsed_seconds=FULL), 'complete')

        assert data['meta'] == {'suggested_break_minutes': 5, 'consecutive_completed': 2}

    def test_otras_acciones_no_devuelven_meta(self, act, make_pomodoro):
        _status, data = act(make_pomodoro(), 'pause')

        assert 'meta' not in data


class TestCompletarRecienAlTerminar:
    """No se puede completar antes de cumplir el foco (con 5 s de tolerancia); las pausas no cuentan."""

    def test_completar_recien_iniciado_da_409(self, act, make_pomodoro):
        pomodoro = make_pomodoro()

        status, data = act(pomodoro, 'complete')

        assert status == 409
        assert data['errors'][0]['detail'] == 'El pomodoro todavía no terminó'
        pomodoro.refresh_from_db()
        assert pomodoro.status == Pomodoro.Status.RUNNING
        assert pomodoro.completed_at is None

    def test_dentro_de_la_tolerancia_de_5_segundos_se_acepta(self, act, make_pomodoro):
        status, _data = act(make_pomodoro(elapsed_seconds=FULL - 4), 'complete')

        assert status == 200

    def test_fuera_de_la_tolerancia_da_409(self, act, make_pomodoro):
        status, _data = act(make_pomodoro(elapsed_seconds=FULL - 30), 'complete')

        assert status == 409

    def test_las_pausas_no_cuentan_como_foco(self, act, make_pomodoro):
        # 25 min desde que arrancó, pero 2 de ellos en pausa: le faltan 2 min de foco.
        status, _data = act(make_pomodoro(elapsed_seconds=FULL, paused_seconds=120), 'complete')

        assert status == 409

    def test_si_el_front_se_demoro_igual_se_puede_completar(self, act, make_pomodoro):
        status, data = act(make_pomodoro(elapsed_seconds=FULL + 600), 'complete')

        assert status == 200
        assert data['data']['attributes']['remaining_seconds'] == 0


class TestRemainingSeconds:

    def test_al_iniciar_queda_la_duracion_completa(self, call, focus_user, active_session):
        _status, data = call(
            pomodoros, 'post', '/', focus_user.user, _start_payload(focus_user.task_a.id), session_id=active_session.id,
        )

        assert FULL - 2 <= data['data']['attributes']['remaining_seconds'] <= FULL

    def test_pausar_congela_el_restante(self, act, make_pomodoro):
        status, data = act(make_pomodoro(elapsed_seconds=600), 'pause')

        assert status == 200
        assert FULL - 602 <= data['data']['attributes']['remaining_seconds'] <= FULL - 600

    def test_reanudar_no_descuenta_el_tiempo_en_pausa(self, act, make_pomodoro):
        # Arrancó hace 15 min, de los cuales los últimos 5 estuvo en pausa: lleva 10 min de foco.
        pomodoro = make_pomodoro(status=Pomodoro.Status.PAUSED, elapsed_seconds=900)
        Pomodoro.objects.filter(id=pomodoro.id).update(paused_at=timezone.now() - timedelta(seconds=300))

        status, data = act(pomodoro, 'resume')

        assert status == 200
        assert FULL - 602 <= data['data']['attributes']['remaining_seconds'] <= FULL - 600

    def test_cancelar_un_pausado_no_cuenta_la_pausa_como_foco(self, act, make_pomodoro):
        pomodoro = make_pomodoro(status=Pomodoro.Status.PAUSED, elapsed_seconds=900)
        Pomodoro.objects.filter(id=pomodoro.id).update(paused_at=timezone.now() - timedelta(seconds=300))

        status, _data = act(pomodoro, 'cancel')

        assert status == 200
        pomodoro.refresh_from_db()
        assert pomodoro.ended_at is not None
        assert 600 <= pomodoro.focus_seconds() <= 602


class TestPomodoroSobreTareaCompletada:

    def test_tarea_done_da_409(self, call, focus_user, active_session):
        focus_user.task_a.status = Task.Status.DONE
        focus_user.task_a.save()

        status, data = call(
            pomodoros, 'post', '/', focus_user.user, _start_payload(focus_user.task_a.id), session_id=active_session.id,
        )

        assert status == 409
        assert data['errors'][0]['detail'] == 'Esa tarea ya está completada'
        assert not Pomodoro.objects.exists()


class TestCambiarTareaDelPomodoro:
    """PATCH action='switch_task': pasa el pomodoro en curso a otra tarea de la sesión."""

    def _switch(self, call, focus_user, active_session, pomodoro, task_id):
        return call(
            pomodoro_detail, 'patch', '/', focus_user.user, _switch_payload(task_id),
            session_id=active_session.id, pomodoro_id=pomodoro.id,
        )

    def test_cambia_la_tarea_de_un_pomodoro_corriendo(self, call, focus_user, active_session, make_pomodoro):
        pomodoro = make_pomodoro(task=focus_user.task_a)

        status, data = self._switch(call, focus_user, active_session, pomodoro, focus_user.task_b.id)

        assert status == 200
        assert data['data']['attributes']['task_id'] == focus_user.task_b.id
        assert 'remaining_seconds' in data['data']['attributes']
        pomodoro.refresh_from_db()
        assert pomodoro.task_id == focus_user.task_b.id

    def test_tambien_funciona_pausado(self, call, focus_user, active_session, make_pomodoro):
        pomodoro = make_pomodoro(status=Pomodoro.Status.PAUSED, task=focus_user.task_a)

        status, _data = self._switch(call, focus_user, active_session, pomodoro, focus_user.task_b.id)

        assert status == 200

    def test_sin_task_id_da_400(self, call, focus_user, active_session, make_pomodoro):
        pomodoro = make_pomodoro()

        status, data = self._switch(call, focus_user, active_session, pomodoro, None)

        assert status == 400

    def test_tarea_fuera_de_la_sesion_da_400(self, call, focus_user, active_session, make_pomodoro):
        pomodoro = make_pomodoro()
        ajena = Task.objects.create(project=focus_user.project, title='Ajena')

        status, data = self._switch(call, focus_user, active_session, pomodoro, ajena.id)

        assert status == 400
        assert data['errors'][0]['detail'] == 'Esa tarea no forma parte del objetivo de esta sesión'

    def test_tarea_completada_da_409(self, call, focus_user, active_session, make_pomodoro):
        pomodoro = make_pomodoro(task=focus_user.task_a)
        focus_user.task_b.status = Task.Status.DONE
        focus_user.task_b.save()

        status, data = self._switch(call, focus_user, active_session, pomodoro, focus_user.task_b.id)

        assert status == 409
        assert data['errors'][0]['detail'] == 'Esa tarea ya está completada'

    def test_tarea_bloqueada_da_409(self, call, focus_user, active_session, make_pomodoro):
        pomodoro = make_pomodoro(task=focus_user.task_a)
        # task_b queda bloqueada por una dependencia FS con una tarea sin completar.
        bloqueante = Task.objects.create(project=focus_user.project, title='Bloqueante')
        TaskDependency.objects.create(
            blocking_task=bloqueante, blocked_task=focus_user.task_b,
            dependency_type=TaskDependency.Type.FINISH_TO_START,
        )

        status, data = self._switch(call, focus_user, active_session, pomodoro, focus_user.task_b.id)

        assert status == 409
        assert data['errors'][0]['detail'] == 'Esa tarea está bloqueada por otra tarea'

    def test_pomodoro_ya_terminado_da_409(self, call, focus_user, active_session, make_pomodoro):
        pomodoro = make_pomodoro(status=Pomodoro.Status.COMPLETED, task=focus_user.task_a)

        status, data = self._switch(call, focus_user, active_session, pomodoro, focus_user.task_b.id)

        assert status == 409
        assert data['errors'][0]['detail'] == 'Solo se puede cambiar la tarea de un pomodoro en curso'
