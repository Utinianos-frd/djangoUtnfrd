import pytest
from django.db import IntegrityError, transaction

from app.tasks.models import Project, Task, TaskDependency
from app.tasks.views.dependency_view import dependencies, dependency_detail

pytestmark = pytest.mark.django_db


def _dependency_payload(blocking, blocked, dependency_type='FS'):
    return {"data": {"type": "task_dependencies", "attributes": {
        "blocking_task_id": blocking.id,
        "blocked_task_id": blocked.id,
        "dependency_type": dependency_type,
    }}}


def _depend(blocking, blocked, dependency_type=TaskDependency.Type.FINISH_TO_START):
    return TaskDependency.objects.create(blocking_task=blocking, blocked_task=blocked, dependency_type=dependency_type)


class TestCrearDependencia:

    def test_group_lead_crea_dependencia(self, call, org_group, project_kwargs, make_task):
        a, b = make_task('A'), make_task('B')

        status, data = call(dependencies, 'post', '/', org_group.lead, _dependency_payload(a, b, 'FF'), **project_kwargs)

        assert status == 201
        attributes = data['data']['attributes']
        assert attributes['blocking_task_title'] == 'A'
        assert attributes['blocked_task_title'] == 'B'
        assert attributes['dependency_type'] == 'FF'

    @pytest.mark.parametrize('role', ['owner', 'contributor'])
    def test_solo_el_group_lead_puede_crear(self, call, org_group, project_kwargs, make_task, role):
        a, b = make_task('A', assignees=[org_group.contributor]), make_task('B')

        status, _data = call(dependencies, 'post', '/', getattr(org_group, role), _dependency_payload(a, b), **project_kwargs)

        assert status == 403

    def test_una_tarea_no_puede_depender_de_si_misma(self, call, org_group, project_kwargs, make_task):
        a = make_task('A')

        status, _data = call(dependencies, 'post', '/', org_group.lead, _dependency_payload(a, a), **project_kwargs)

        assert status == 400

    def test_duplicada_da_409(self, call, org_group, project_kwargs, make_task):
        a, b = make_task('A'), make_task('B')
        _depend(a, b)

        status, _data = call(dependencies, 'post', '/', org_group.lead, _dependency_payload(a, b, 'FF'), **project_kwargs)

        assert status == 409

    def test_tipo_invalido_da_400(self, call, org_group, project_kwargs, make_task):
        a, b = make_task('A'), make_task('B')

        status, _data = call(dependencies, 'post', '/', org_group.lead, _dependency_payload(a, b, 'XX'), **project_kwargs)

        assert status == 400

    def test_tarea_de_otro_proyecto_da_404(self, call, org_group, project_kwargs, make_task):
        other_project = Project.objects.create(group=org_group.group, name='Otro')
        a = make_task('A')
        foreign = make_task('Ajena', project=other_project)

        status, _data = call(dependencies, 'post', '/', org_group.lead, _dependency_payload(a, foreign), **project_kwargs)

        assert status == 404
        assert not TaskDependency.objects.exists()


class TestDeteccionDeCiclos:
    """RF-34: no se puede crear una dependencia que cierre un ciclo, directo o transitivo."""

    def test_ciclo_directo(self, call, org_group, project_kwargs, make_task):
        a, b = make_task('A'), make_task('B')
        _depend(a, b)

        status, data = call(dependencies, 'post', '/', org_group.lead, _dependency_payload(b, a), **project_kwargs)

        assert status == 400
        assert 'ciclo' in data['errors'][0]['detail']

    def test_ciclo_transitivo(self, call, org_group, project_kwargs, make_task):
        a, b, c, d = (make_task(t) for t in 'ABCD')
        _depend(a, b)
        _depend(b, c)
        _depend(c, d)

        status, _data = call(dependencies, 'post', '/', org_group.lead, _dependency_payload(d, a), **project_kwargs)

        assert status == 400
        assert TaskDependency.objects.count() == 3

    def test_diamante_no_es_ciclo(self, call, org_group, project_kwargs, make_task):
        # A -> B -> D y A -> C; agregar C -> D cierra un diamante, no un ciclo.
        a, b, c, d = (make_task(t) for t in 'ABCD')
        _depend(a, b)
        _depend(b, d)
        _depend(a, c)

        status, _data = call(dependencies, 'post', '/', org_group.lead, _dependency_payload(c, d), **project_kwargs)

        assert status == 201


class TestListarDependencias:

    @pytest.mark.parametrize('role', ['owner', 'admin', 'lead'])
    def test_owner_admin_y_lead_ven_todas(self, call, org_group, project_kwargs, make_task, role):
        a, b, c = make_task('A'), make_task('B'), make_task('C')
        _depend(a, b)
        _depend(b, c)

        status, data = call(dependencies, 'get', '/', getattr(org_group, role), **project_kwargs)

        assert status == 200
        assert len(data['data']) == 2

    def test_contributor_ve_solo_las_que_tocan_sus_tareas(self, call, org_group, project_kwargs, make_task):
        mine = make_task('Mía', assignees=[org_group.contributor])
        a, b = make_task('A'), make_task('B')
        _depend(a, mine)
        _depend(a, b)

        status, data = call(dependencies, 'get', '/', org_group.contributor, **project_kwargs)

        assert status == 200
        assert [d['attributes']['blocked_task_title'] for d in data['data']] == ['Mía']

    def test_quien_no_esta_en_el_grupo_da_403(self, call, org_group, project_kwargs):
        status, _data = call(dependencies, 'get', '/', org_group.member, **project_kwargs)

        assert status == 403


class TestEliminarDependencia:

    def test_group_lead_elimina(self, call, org_group, project_kwargs, make_task):
        dependency = _depend(make_task('A'), make_task('B'))

        status, _data = call(
            dependency_detail, 'delete', '/', org_group.lead, dependency_id=dependency.id, **project_kwargs,
        )

        assert status == 204
        assert not TaskDependency.objects.exists()

    def test_contributor_no_puede_eliminar(self, call, org_group, project_kwargs, make_task):
        dependency = _depend(make_task('A', assignees=[org_group.contributor]), make_task('B'))

        status, _data = call(
            dependency_detail, 'delete', '/', org_group.contributor, dependency_id=dependency.id, **project_kwargs,
        )

        assert status == 403
        assert TaskDependency.objects.exists()

    def test_inexistente_da_404(self, call, org_group, project_kwargs):
        status, _data = call(dependency_detail, 'delete', '/', org_group.lead, dependency_id=999, **project_kwargs)

        assert status == 404

    def test_borrar_una_tarea_borra_sus_dependencias(self, org_group, make_task):
        a = make_task('A')
        _depend(a, make_task('B'))

        a.delete()

        assert not TaskDependency.objects.exists()


class TestConstraintsDeBase:

    def test_unique_por_par_de_tareas(self, make_task):
        a, b = make_task('A'), make_task('B')
        _depend(a, b)

        with pytest.raises(IntegrityError), transaction.atomic():
            _depend(a, b, TaskDependency.Type.FINISH_TO_FINISH)

    def test_no_self_dependency(self, make_task):
        a = make_task('A')

        with pytest.raises(IntegrityError), transaction.atomic():
            _depend(a, a)


def test_borrar_el_proyecto_borra_tareas_y_dependencias(org_group, make_task):
    _depend(make_task('A'), make_task('B'))

    org_group.project.delete()

    assert not Task.objects.exists()
    assert not TaskDependency.objects.exists()
