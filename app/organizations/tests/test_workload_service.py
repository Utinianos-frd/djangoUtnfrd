from types import SimpleNamespace

import pytest

from app.organizations.models import Membership, Group, GroupMembership
from app.organizations.services.workload_service import clasificar, advertencias_de_asignacion
from app.organizations.views.workload_view import workload, workload_member_detail
from app.tasks.models import Project, Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def wl(owner_org, make_user):
    """Org (umbral 3) con un grupo Backend: lead, ana y beto como contributors; más un admin, un member
    sin grupo y un lead de otro grupo (Frontend) de la misma org, donde ana también participa."""
    organization, owner = owner_org
    organization.overload_threshold = 3
    organization.save()

    users = {name: make_user(name) for name in ('admin', 'member', 'lead', 'ana', 'beto', 'front_lead')}
    Membership.objects.create(organization=organization, user=users['admin'], role=Membership.Role.ADMIN)
    for name in ('member', 'lead', 'ana', 'beto', 'front_lead'):
        Membership.objects.create(organization=organization, user=users[name], role=Membership.Role.MEMBER)

    backend = Group.objects.create(organization=organization, name='Backend')
    GroupMembership.objects.create(group=backend, user=users['lead'], role=GroupMembership.Role.GROUP_LEAD)
    GroupMembership.objects.create(group=backend, user=users['ana'], role=GroupMembership.Role.CONTRIBUTOR)
    GroupMembership.objects.create(group=backend, user=users['beto'], role=GroupMembership.Role.CONTRIBUTOR)

    frontend = Group.objects.create(organization=organization, name='Frontend')
    GroupMembership.objects.create(group=frontend, user=users['front_lead'], role=GroupMembership.Role.GROUP_LEAD)
    GroupMembership.objects.create(group=frontend, user=users['ana'], role=GroupMembership.Role.CONTRIBUTOR)

    return SimpleNamespace(
        organization=organization, owner=owner, backend=backend, frontend=frontend,
        backend_project=Project.objects.create(group=backend, name='API'),
        frontend_project=Project.objects.create(group=frontend, name='Web'),
        **users,
    )


@pytest.fixture
def assign(wl):
    """Crea una tarea asignada a `user` en el proyecto indicado (Backend por defecto)."""

    def _assign(user, status=Task.Status.PENDING, project=None, title='Tarea'):
        task = Task.objects.create(project=project or wl.backend_project, title=title, status=status)
        task.assignees.set([user])
        return task

    return _assign


def _kwargs(wl, group=None):
    return {'organization_id': wl.organization.id, 'group_id': (group or wl.backend).id}


def _rows_by_username(data):
    return {row['attributes']['username']: row['attributes'] for row in data['data']}


class TestClasificar:

    @pytest.mark.parametrize('count, threshold, expected', [
        (0, 3, 'available'),
        (1, 3, 'busy'),
        (2, 3, 'busy'),
        (3, 3, 'overloaded'),  # el umbral es inclusivo: llegar al umbral ya es sobrecarga
        (10, 3, 'overloaded'),
        (0, 0, 'available'),   # sin tareas nunca es sobrecarga, aunque el umbral sea 0
    ])
    def test_clasifica_segun_el_umbral(self, count, threshold, expected):
        assert clasificar(count, threshold) == expected


class TestPanelWorkload:

    @pytest.mark.parametrize('role', ['owner', 'admin', 'lead'])
    def test_owner_admin_y_lead_del_grupo_pueden_verlo(self, call, wl, role):
        status, data = call(workload, 'get', '/', getattr(wl, role), **_kwargs(wl))

        assert status == 200
        assert set(_rows_by_username(data)) == {'lead', 'ana', 'beto'}  # incluye al group lead

    @pytest.mark.parametrize('role', ['ana', 'member', 'front_lead'])
    def test_contributor_member_o_lead_de_otro_grupo_no_pueden(self, call, wl, role):
        status, _data = call(workload, 'get', '/', getattr(wl, role), **_kwargs(wl))

        assert status == 403

    def test_grupo_de_otra_organizacion_da_404(self, call, wl):
        status, _data = call(
            workload, 'get', '/', wl.owner, organization_id=wl.organization.id + 999, group_id=wl.backend.id,
        )

        assert status == 404

    def test_cuenta_solo_tareas_activas_y_clasifica(self, call, wl, assign):
        assign(wl.ana, Task.Status.PENDING)
        assign(wl.ana, Task.Status.IN_PROGRESS)
        assign(wl.ana, Task.Status.IN_PROGRESS)
        assign(wl.ana, Task.Status.DONE)  # 'done' no suma
        assign(wl.beto, Task.Status.PENDING)

        _status, data = call(workload, 'get', '/', wl.lead, **_kwargs(wl))
        rows = _rows_by_username(data)

        assert rows['ana']['active_task_count'] == 3
        assert rows['ana']['status'] == 'overloaded'
        assert rows['beto']['active_task_count'] == 1
        assert rows['beto']['status'] == 'busy'
        assert rows['lead']['active_task_count'] == 0
        assert rows['lead']['status'] == 'available'
        assert rows['ana']['group_role'] == 'contributor'

    def test_la_carga_es_global_entre_grupos(self, call, wl, assign):
        assign(wl.ana, project=wl.backend_project)
        assign(wl.ana, project=wl.frontend_project)
        assign(wl.ana, project=wl.frontend_project)

        _status, data = call(workload, 'get', '/', wl.lead, **_kwargs(wl))

        assert _rows_by_username(data)['ana']['active_task_count'] == 3
        assert _rows_by_username(data)['ana']['status'] == 'overloaded'

    def test_tarea_con_varios_asignados_cuenta_para_cada_uno(self, call, wl):
        task = Task.objects.create(project=wl.backend_project, title='Pair')
        task.assignees.set([wl.ana, wl.beto])

        _status, data = call(workload, 'get', '/', wl.lead, **_kwargs(wl))
        rows = _rows_by_username(data)

        assert rows['ana']['active_task_count'] == 1
        assert rows['beto']['active_task_count'] == 1

    def test_cambiar_el_umbral_reclasifica(self, call, wl, assign):
        assign(wl.beto)
        assign(wl.beto)
        wl.organization.overload_threshold = 2
        wl.organization.save()

        _status, data = call(workload, 'get', '/', wl.lead, **_kwargs(wl))

        assert _rows_by_username(data)['beto']['status'] == 'overloaded'


class TestDetalleMiembro:

    def test_lista_tareas_activas_incluso_de_otros_grupos(self, call, wl, assign):
        backend_task = assign(wl.ana, project=wl.backend_project, title='Login')
        front_task = assign(wl.ana, Task.Status.IN_PROGRESS, project=wl.frontend_project, title='Navbar')
        assign(wl.ana, Task.Status.DONE, title='Vieja')

        status, data = call(workload_member_detail, 'get', '/', wl.lead, user_id=wl.ana.id, **_kwargs(wl))

        assert status == 200
        attributes = data['data']['attributes']
        assert attributes['active_task_count'] == 2
        assert attributes['status'] == 'busy'
        tasks = {t['task_id']: t for t in attributes['active_tasks']}
        assert set(tasks) == {backend_task.id, front_task.id}
        assert tasks[front_task.id]['group_id'] == wl.frontend.id
        assert tasks[front_task.id]['project_id'] == wl.frontend_project.id

    def test_usuario_que_no_es_del_grupo_da_404(self, call, wl):
        status, _data = call(workload_member_detail, 'get', '/', wl.lead, user_id=wl.member.id, **_kwargs(wl))

        assert status == 404

    def test_sin_permiso_da_403(self, call, wl):
        status, _data = call(workload_member_detail, 'get', '/', wl.ana, user_id=wl.beto.id, **_kwargs(wl))

        assert status == 403


class TestAdvertenciasDeAsignacion:
    """RF-42/43: advertencia no bloqueante si el asignado queda sobrecargado, con hasta 3 alternativas libres."""

    def test_sin_asignados_no_hay_advertencias(self, wl):
        assert advertencias_de_asignacion(wl.organization, wl.backend, []) == []

    def test_asignado_no_sobrecargado_no_genera_advertencia(self, wl, assign):
        assign(wl.ana)

        assert advertencias_de_asignacion(wl.organization, wl.backend, [wl.ana.id]) == []

    def test_sobrecargado_genera_advertencia_con_alternativas_disponibles(self, wl, assign):
        for _ in range(3):
            assign(wl.ana)
        assign(wl.beto)  # beto está 'busy', no 'available': no se sugiere

        warnings = advertencias_de_asignacion(wl.organization, wl.backend, [wl.ana.id])

        assert len(warnings) == 1
        assert warnings[0]['user_id'] == wl.ana.id
        assert warnings[0]['active_task_count'] == 3
        assert warnings[0]['suggested_alternatives'] == ['lead']

    def test_no_sugiere_a_los_propios_asignados(self, wl, assign):
        for _ in range(3):
            assign(wl.ana)

        warnings = advertencias_de_asignacion(wl.organization, wl.backend, [wl.ana.id, wl.lead.id])

        assert len(warnings) == 1  # el lead no está sobrecargado
        assert 'lead' not in warnings[0]['suggested_alternatives']
        assert warnings[0]['suggested_alternatives'] == ['beto']

    def test_ids_que_no_son_del_grupo_se_ignoran(self, wl, assign):
        for _ in range(3):
            assign(wl.member)

        assert advertencias_de_asignacion(wl.organization, wl.backend, [wl.member.id]) == []

    def test_como_maximo_tres_alternativas(self, wl, assign, make_user):
        for name in ('c1', 'c2', 'c3'):
            user = make_user(name)
            GroupMembership.objects.create(group=wl.backend, user=user, role=GroupMembership.Role.CONTRIBUTOR)
        for _ in range(3):
            assign(wl.ana)

        warnings = advertencias_de_asignacion(wl.organization, wl.backend, [wl.ana.id])

        assert len(warnings[0]['suggested_alternatives']) == 3
