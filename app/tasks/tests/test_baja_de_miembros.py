"""Quien sale de un grupo u organización pierde el acceso a las tareas que tenía asignadas.

Antes, la baja borraba solo la membresía: las asignaciones quedaban y seguían habilitando ver la tarea,
comentarla o cambiarle el status; y la baja de la organización ni siquiera lo sacaba de sus grupos.
"""
import pytest

from app.organizations.models import Group, GroupMembership, Membership
from app.organizations.views.group_membership_view import group_member_detail
from app.organizations.views.membership_view import member_detail
from app.tasks.models import Project, Task
from app.tasks.views.comment_view import comments
from app.tasks.views.task_view import task_detail

pytestmark = pytest.mark.django_db


def _sacar_del_grupo(call, org_group, actor, user):
    return call(
        group_member_detail, 'delete', '/', actor,
        organization_id=org_group.organization.id, group_id=org_group.group.id, user_id=user.id,
    )


def _sacar_de_la_org(call, org_group, actor, user):
    return call(member_detail, 'delete', '/', actor, organization_id=org_group.organization.id, user_id=user.id)


def _sin_acceso_a_la_tarea(call, user, task, project_kwargs):
    """Verifica las tres vías por las que una asignación vieja daba acceso."""
    get_status, _ = call(task_detail, 'get', '/', user, task_id=task.id, **project_kwargs)
    patch_status, _ = call(
        task_detail, 'patch', '/', user, {"data": {"type": "tasks", "attributes": {"status": "in_progress"}}},
        task_id=task.id, **project_kwargs,
    )
    comment_status, _ = call(
        comments, 'post', '/', user, {"data": {"type": "comments", "attributes": {"text": "hola"}}},
        task_id=task.id, **project_kwargs,
    )
    return (get_status, patch_status, comment_status) == (403, 403, 403)


class TestBajaDelGrupo:

    def test_le_quita_las_asignaciones_y_el_acceso(self, call, org_group, project_kwargs, make_task):
        task = make_task(assignees=[org_group.contributor, org_group.contributor2])

        status, _ = _sacar_del_grupo(call, org_group, org_group.lead, org_group.contributor)

        assert status == 204
        assert list(task.assignees.all()) == [org_group.contributor2]  # al resto no se lo toca
        assert _sin_acceso_a_la_tarea(call, org_group.contributor, task, project_kwargs)

    def test_no_toca_asignaciones_de_otros_grupos(self, call, org_group, make_task):
        other_group = Group.objects.create(organization=org_group.organization, name='Frontend')
        GroupMembership.objects.create(group=other_group, user=org_group.contributor, role=GroupMembership.Role.CONTRIBUTOR)
        other_task = make_task(
            project=Project.objects.create(group=other_group, name='Web'), assignees=[org_group.contributor],
        )

        _sacar_del_grupo(call, org_group, org_group.lead, org_group.contributor)

        assert other_task.assignees.filter(id=org_group.contributor.id).exists()


class TestBajaDeLaOrganizacion:

    def test_lo_saca_de_sus_grupos_y_le_quita_las_asignaciones(self, call, org_group, project_kwargs, make_task):
        task = make_task(assignees=[org_group.contributor])

        status, _ = _sacar_de_la_org(call, org_group, org_group.owner, org_group.contributor)

        assert status == 204
        assert not GroupMembership.objects.filter(user=org_group.contributor).exists()
        assert not task.assignees.exists()
        assert _sin_acceso_a_la_tarea(call, org_group.contributor, task, project_kwargs)

    def test_no_se_puede_dar_de_baja_a_un_group_lead(self, call, org_group):
        status, data = _sacar_de_la_org(call, org_group, org_group.owner, org_group.lead)

        assert status == 400
        assert 'group lead' in data['errors'][0]['detail']
        assert Membership.objects.filter(user=org_group.lead).exists()
        assert GroupMembership.objects.filter(user=org_group.lead, role=GroupMembership.Role.GROUP_LEAD).exists()


class TestAsignacionColgada:
    """Segunda barrera: aunque quede una asignación vieja en la base (datos previos al fix), no da acceso."""

    def test_asignado_que_ya_no_es_del_grupo_no_tiene_acceso(self, call, org_group, project_kwargs, make_task):
        task = make_task(assignees=[org_group.contributor])
        GroupMembership.objects.filter(user=org_group.contributor).delete()  # baja "vieja", sin limpiar asignaciones

        assert task.assignees.filter(id=org_group.contributor.id).exists()
        assert _sin_acceso_a_la_tarea(call, org_group.contributor, task, project_kwargs)
        assert Task.objects.get(id=task.id).status == Task.Status.PENDING
