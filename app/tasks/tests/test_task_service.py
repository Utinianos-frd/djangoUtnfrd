import pytest

from app.tasks.models import Task, TaskDependency
from app.tasks.views.task_view import tasks, task_detail

pytestmark = pytest.mark.django_db


def _task_payload(**attrs):
    return {"data": {"type": "tasks", "attributes": attrs}}


class TestCrearTarea:

    def test_group_lead_crea_tarea_con_asignados(self, call, org_group, project_kwargs):
        status, data = call(
            tasks, 'post', '/', org_group.lead,
            _task_payload(title='Login', assignee_ids=[org_group.contributor.id]), **project_kwargs,
        )

        assert status == 201
        attributes = data['data']['attributes']
        assert attributes['title'] == 'Login'
        assert attributes['status'] == Task.Status.PENDING
        assert attributes['assignee_ids'] == [org_group.contributor.id]
        assert attributes['blocked'] is False
        assert 'meta' not in data

    def test_puede_crearse_sin_asignados(self, call, org_group, project_kwargs):
        status, data = call(tasks, 'post', '/', org_group.lead, _task_payload(title='Login'), **project_kwargs)

        assert status == 201
        assert data['data']['attributes']['assignee_ids'] == []

    @pytest.mark.parametrize('role', ['owner', 'admin', 'contributor'])
    def test_solo_el_group_lead_puede_crear(self, call, org_group, project_kwargs, role):
        status, _data = call(tasks, 'post', '/', getattr(org_group, role), _task_payload(title='Login'), **project_kwargs)

        assert status == 403

    def test_asignado_que_no_es_del_grupo_da_400(self, call, org_group, project_kwargs):
        status, _data = call(
            tasks, 'post', '/', org_group.lead,
            _task_payload(title='Login', assignee_ids=[org_group.member.id]), **project_kwargs,
        )

        assert status == 400
        assert not Task.objects.exists()

    def test_titulo_faltante_da_400(self, call, org_group, project_kwargs):
        status, data = call(tasks, 'post', '/', org_group.lead, _task_payload(), **project_kwargs)

        assert status == 400
        assert data['errors'][0]['source']['pointer'] == '/data/attributes/title'

    def test_asignar_a_alguien_sobrecargado_devuelve_warning_sin_bloquear(
        self, call, org_group, project_kwargs, make_task,
    ):
        org_group.organization.overload_threshold = 2
        org_group.organization.save()
        make_task(assignees=[org_group.contributor])

        status, data = call(
            tasks, 'post', '/', org_group.lead,
            _task_payload(title='Otra', assignee_ids=[org_group.contributor.id]), **project_kwargs,
        )

        assert status == 201
        warning = data['meta']['warnings'][0]
        assert warning['user_id'] == org_group.contributor.id
        assert warning['active_task_count'] == 2
        assert set(warning['suggested_alternatives']) == {'lead', 'contributor2'}


class TestListarTareas:

    @pytest.mark.parametrize('role', ['owner', 'admin', 'lead'])
    def test_owner_admin_y_lead_ven_todas(self, call, org_group, project_kwargs, make_task, role):
        make_task('A', assignees=[org_group.contributor])
        make_task('B')

        status, data = call(tasks, 'get', '/', getattr(org_group, role), **project_kwargs)

        assert status == 200
        assert sorted(t['attributes']['title'] for t in data['data']) == ['A', 'B']

    def test_contributor_ve_solo_sus_tareas(self, call, org_group, project_kwargs, make_task):
        make_task('Mía', assignees=[org_group.contributor, org_group.contributor2])
        make_task('Ajena', assignees=[org_group.contributor2])

        status, data = call(tasks, 'get', '/', org_group.contributor, **project_kwargs)

        assert status == 200
        assert [t['attributes']['title'] for t in data['data']] == ['Mía']

    @pytest.mark.parametrize('role', ['member', 'outsider'])
    def test_quien_no_esta_en_el_grupo_da_403(self, call, org_group, project_kwargs, role):
        status, _data = call(tasks, 'get', '/', getattr(org_group, role), **project_kwargs)

        assert status == 403


class TestVerTarea:

    def test_contributor_asignado_ve_la_tarea(self, call, org_group, project_kwargs, make_task):
        task = make_task(assignees=[org_group.contributor])

        status, data = call(task_detail, 'get', '/', org_group.contributor, task_id=task.id, **project_kwargs)

        assert status == 200
        assert data['data']['id'] == str(task.id)

    def test_contributor_no_asignado_da_403(self, call, org_group, project_kwargs, make_task):
        task = make_task(assignees=[org_group.contributor2])

        status, _data = call(task_detail, 'get', '/', org_group.contributor, task_id=task.id, **project_kwargs)

        assert status == 403

    def test_tarea_inexistente_da_404(self, call, org_group, project_kwargs):
        status, _data = call(task_detail, 'get', '/', org_group.lead, task_id=999, **project_kwargs)

        assert status == 404


class TestActualizarTarea:

    def test_group_lead_edita_titulo_estado_y_asignados(self, call, org_group, project_kwargs, make_task):
        task = make_task(assignees=[org_group.contributor])

        status, data = call(
            task_detail, 'patch', '/', org_group.lead,
            _task_payload(title='Nuevo', status='in_progress', assignee_ids=[org_group.contributor2.id]),
            task_id=task.id, **project_kwargs,
        )

        assert status == 200
        attributes = data['data']['attributes']
        assert attributes['title'] == 'Nuevo'
        assert attributes['status'] == 'in_progress'
        assert attributes['assignee_ids'] == [org_group.contributor2.id]

    def test_group_lead_no_puede_asignar_a_alguien_fuera_del_grupo(
        self, call, org_group, project_kwargs, make_task,
    ):
        task = make_task()

        status, _data = call(
            task_detail, 'patch', '/', org_group.lead,
            _task_payload(assignee_ids=[org_group.outsider.id]), task_id=task.id, **project_kwargs,
        )

        assert status == 400
        assert task.assignees.count() == 0

    def test_status_invalido_da_400(self, call, org_group, project_kwargs, make_task):
        task = make_task()

        status, _data = call(
            task_detail, 'patch', '/', org_group.lead, _task_payload(status='archivada'),
            task_id=task.id, **project_kwargs,
        )

        assert status == 400

    def test_contributor_asignado_cambia_el_status(self, call, org_group, project_kwargs, make_task):
        task = make_task(assignees=[org_group.contributor])

        status, data = call(
            task_detail, 'patch', '/', org_group.contributor, _task_payload(status='done'),
            task_id=task.id, **project_kwargs,
        )

        assert status == 200
        assert data['data']['attributes']['status'] == 'done'

    def test_contributor_no_puede_cambiar_el_titulo(self, call, org_group, project_kwargs, make_task):
        task = make_task(assignees=[org_group.contributor])

        status, _data = call(
            task_detail, 'patch', '/', org_group.contributor, _task_payload(title='Hackeado', status='done'),
            task_id=task.id, **project_kwargs,
        )

        assert status == 400
        task.refresh_from_db()
        assert task.title == 'Tarea'
        assert task.status == Task.Status.PENDING

    def test_contributor_no_asignado_da_403(self, call, org_group, project_kwargs, make_task):
        task = make_task(assignees=[org_group.contributor2])

        status, _data = call(
            task_detail, 'patch', '/', org_group.contributor, _task_payload(status='done'),
            task_id=task.id, **project_kwargs,
        )

        assert status == 403

    def test_owner_no_puede_editar_tareas(self, call, org_group, project_kwargs, make_task):
        task = make_task()

        status, _data = call(
            task_detail, 'patch', '/', org_group.owner, _task_payload(status='done'),
            task_id=task.id, **project_kwargs,
        )

        assert status == 403


class TestBloqueoPorDependencias:
    """RF-33: el status de la tarea bloqueada no puede avanzar mientras la bloqueante no esté 'done'."""

    def _depend(self, blocking, blocked, dependency_type):
        TaskDependency.objects.create(blocking_task=blocking, blocked_task=blocked, dependency_type=dependency_type)

    def _patch_status(self, call, user, task, new_status, project_kwargs):
        return call(
            task_detail, 'patch', '/', user, _task_payload(status=new_status),
            task_id=task.id, **project_kwargs,
        )

    def test_fs_impide_arrancar_y_marca_blocked(self, call, org_group, project_kwargs, make_task):
        blocking = make_task('Diseño')
        blocked = make_task('Implementación', assignees=[org_group.contributor])
        self._depend(blocking, blocked, TaskDependency.Type.FINISH_TO_START)

        status, data = self._patch_status(call, org_group.contributor, blocked, 'in_progress', project_kwargs)
        _s, detail = call(task_detail, 'get', '/', org_group.lead, task_id=blocked.id, **project_kwargs)

        assert status == 409
        assert 'Diseño' in data['errors'][0]['detail']
        assert detail['data']['attributes']['blocked'] is True

    def test_fs_tambien_frena_al_group_lead(self, call, org_group, project_kwargs, make_task):
        blocking = make_task('Diseño')
        blocked = make_task('Implementación')
        self._depend(blocking, blocked, TaskDependency.Type.FINISH_TO_START)

        status, _data = self._patch_status(call, org_group.lead, blocked, 'done', project_kwargs)

        assert status == 409

    def test_fs_se_libera_cuando_la_bloqueante_esta_done(self, call, org_group, project_kwargs, make_task):
        blocking = make_task('Diseño', status=Task.Status.DONE)
        blocked = make_task('Implementación')
        self._depend(blocking, blocked, TaskDependency.Type.FINISH_TO_START)

        status, data = self._patch_status(call, org_group.lead, blocked, 'in_progress', project_kwargs)

        assert status == 200
        assert data['data']['attributes']['blocked'] is False

    def test_ff_permite_arrancar_pero_no_completar(self, call, org_group, project_kwargs, make_task):
        blocking = make_task('Backend')
        blocked = make_task('Frontend')
        self._depend(blocking, blocked, TaskDependency.Type.FINISH_TO_FINISH)

        start_status, start_data = self._patch_status(call, org_group.lead, blocked, 'in_progress', project_kwargs)
        done_status, _data = self._patch_status(call, org_group.lead, blocked, 'done', project_kwargs)

        assert start_status == 200
        assert start_data['data']['attributes']['blocked'] is False  # el candado es solo para FS
        assert done_status == 409


class TestEliminarTarea:

    def test_group_lead_elimina(self, call, org_group, project_kwargs, make_task):
        task = make_task()

        status, _data = call(task_detail, 'delete', '/', org_group.lead, task_id=task.id, **project_kwargs)

        assert status == 204
        assert not Task.objects.filter(id=task.id).exists()

    @pytest.mark.parametrize('role', ['owner', 'contributor'])
    def test_otros_roles_no_pueden_eliminar(self, call, org_group, project_kwargs, make_task, role):
        task = make_task(assignees=[org_group.contributor])

        status, _data = call(task_detail, 'delete', '/', getattr(org_group, role), task_id=task.id, **project_kwargs)

        assert status == 403
        assert Task.objects.filter(id=task.id).exists()
