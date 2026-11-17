import pytest

from app.tasks.models import Project, Task
from app.tasks.views.project_view import projects, project_detail

pytestmark = pytest.mark.django_db


def _project_payload(**attrs):
    return {"data": {"type": "projects", "attributes": attrs}}


@pytest.fixture
def group_kwargs(org_group):
    return {'organization_id': org_group.organization.id, 'group_id': org_group.group.id}


class TestCrearProyecto:

    def test_owner_puede_crear_proyecto(self, call, org_group, group_kwargs):
        status, data = call(projects, 'post', '/', org_group.owner, _project_payload(name='Web'), **group_kwargs)

        assert status == 201
        assert data['data']['attributes'] == {'name': 'Web', 'description': '', 'group_id': org_group.group.id}

    def test_owner_puede_crear_proyecto_con_descripcion(self, call, org_group, group_kwargs):
        status, data = call(
            projects, 'post', '/', org_group.owner,
            _project_payload(name='Web', description='Sitio público'), **group_kwargs,
        )

        assert status == 201
        assert data['data']['attributes']['description'] == 'Sitio público'

    @pytest.mark.parametrize('role', ['admin', 'lead', 'contributor'])
    def test_solo_el_owner_puede_crear(self, call, org_group, group_kwargs, role):
        status, _data = call(projects, 'post', '/', getattr(org_group, role), _project_payload(name='Web'), **group_kwargs)

        assert status == 403

    def test_grupo_de_otra_organizacion_da_404(self, call, org_group):
        other_org_id = org_group.organization.id + 999

        status, _data = call(
            projects, 'post', '/', org_group.owner, _project_payload(name='Web'),
            organization_id=other_org_id, group_id=org_group.group.id,
        )

        assert status == 404

    def test_body_sin_formato_jsonapi_da_400(self, call, org_group, group_kwargs):
        status, _data = call(projects, 'post', '/', org_group.owner, {'name': 'Web'}, **group_kwargs)

        assert status == 400

    def test_nombre_faltante_da_400_con_pointer(self, call, org_group, group_kwargs):
        status, data = call(projects, 'post', '/', org_group.owner, _project_payload(), **group_kwargs)

        assert status == 400
        assert data['errors'][0]['source']['pointer'] == '/data/attributes/name'


class TestListarProyectos:

    @pytest.mark.parametrize('role', ['owner', 'admin', 'lead', 'contributor'])
    def test_owner_admin_y_miembros_del_grupo_ven_los_proyectos(self, call, org_group, group_kwargs, role):
        status, data = call(projects, 'get', '/', getattr(org_group, role), **group_kwargs)

        assert status == 200
        assert [p['attributes']['name'] for p in data['data']] == ['API']

    @pytest.mark.parametrize('role', ['member', 'outsider'])
    def test_quien_no_esta_en_el_grupo_no_ve_los_proyectos(self, call, org_group, group_kwargs, role):
        status, _data = call(projects, 'get', '/', getattr(org_group, role), **group_kwargs)

        assert status == 403


class TestVerEditarEliminarProyecto:

    def test_contributor_puede_ver_el_detalle(self, call, org_group, project_kwargs):
        status, data = call(project_detail, 'get', '/', org_group.contributor, **project_kwargs)

        assert status == 200
        assert data['data']['id'] == str(org_group.project.id)

    def test_proyecto_inexistente_da_404(self, call, org_group, project_kwargs):
        project_kwargs['project_id'] += 999

        status, _data = call(project_detail, 'get', '/', org_group.owner, **project_kwargs)

        assert status == 404

    def test_owner_puede_renombrar(self, call, org_group, project_kwargs):
        status, data = call(project_detail, 'patch', '/', org_group.owner, _project_payload(name='API v2'), **project_kwargs)

        assert status == 200
        assert data['data']['attributes']['name'] == 'API v2'
        org_group.project.refresh_from_db()
        assert org_group.project.name == 'API v2'

    def test_owner_edita_la_descripcion_sin_tocar_el_nombre(self, call, org_group, project_kwargs):
        status, data = call(
            project_detail, 'patch', '/', org_group.owner, _project_payload(description='Backend REST'),
            **project_kwargs,
        )

        assert status == 200
        org_group.project.refresh_from_db()
        assert org_group.project.description == 'Backend REST'
        assert org_group.project.name == data['data']['attributes']['name'] == 'API'

    def test_group_lead_no_puede_renombrar(self, call, org_group, project_kwargs):
        status, _data = call(project_detail, 'patch', '/', org_group.lead, _project_payload(name='API v2'), **project_kwargs)

        assert status == 403

    def test_owner_elimina_el_proyecto_y_sus_tareas_en_cascada(self, call, org_group, project_kwargs, make_task):
        make_task()

        status, _data = call(project_detail, 'delete', '/', org_group.owner, **project_kwargs)

        assert status == 204
        assert not Project.objects.filter(id=org_group.project.id).exists()
        assert not Task.objects.exists()

    def test_admin_no_puede_eliminar(self, call, org_group, project_kwargs):
        status, _data = call(project_detail, 'delete', '/', org_group.admin, **project_kwargs)

        assert status == 403
        assert Project.objects.filter(id=org_group.project.id).exists()
