import pytest

from app.tasks.models import Comment
from app.tasks.views.comment_view import comments

pytestmark = pytest.mark.django_db


def _comment_payload(**attrs):
    return {"data": {"type": "comments", "attributes": attrs}}


class TestCrearComentario:

    def test_group_lead_comenta_cualquier_tarea(self, call, org_group, project_kwargs, make_task):
        task = make_task()

        status, data = call(
            comments, 'post', '/', org_group.lead, _comment_payload(text='Revisar'),
            task_id=task.id, **project_kwargs,
        )

        assert status == 201
        assert data['data']['attributes']['text'] == 'Revisar'
        assert data['data']['attributes']['author_username'] == 'lead'

    def test_contributor_asignado_puede_comentar(self, call, org_group, project_kwargs, make_task):
        task = make_task(assignees=[org_group.contributor])

        status, _data = call(
            comments, 'post', '/', org_group.contributor, _comment_payload(text='Listo'),
            task_id=task.id, **project_kwargs,
        )

        assert status == 201

    @pytest.mark.parametrize('role', ['contributor', 'owner', 'admin'])
    def test_no_asignados_ni_lead_no_pueden_comentar(self, call, org_group, project_kwargs, make_task, role):
        task = make_task(assignees=[org_group.contributor2])

        status, _data = call(
            comments, 'post', '/', getattr(org_group, role), _comment_payload(text='Hola'),
            task_id=task.id, **project_kwargs,
        )

        assert status == 403
        assert not Comment.objects.exists()

    def test_texto_faltante_da_400(self, call, org_group, project_kwargs, make_task):
        task = make_task()

        status, _data = call(comments, 'post', '/', org_group.lead, _comment_payload(), task_id=task.id, **project_kwargs)

        assert status == 400

    def test_comentario_de_2000_caracteres_se_acepta(self, call, org_group, project_kwargs, make_task):
        task = make_task()

        status, _data = call(
            comments, 'post', '/', org_group.lead, _comment_payload(text='a' * 2000),
            task_id=task.id, **project_kwargs,
        )

        assert status == 201

    def test_comentario_de_mas_de_2000_caracteres_da_400(self, call, org_group, project_kwargs, make_task):
        task = make_task()

        status, data = call(
            comments, 'post', '/', org_group.lead, _comment_payload(text='a' * 2001),
            task_id=task.id, **project_kwargs,
        )

        assert status == 400
        assert data['errors'][0]['detail'] == 'El comentario no puede superar los 2000 caracteres.'
        assert not Comment.objects.exists()

    def test_tarea_inexistente_da_404(self, call, org_group, project_kwargs):
        status, _data = call(
            comments, 'post', '/', org_group.lead, _comment_payload(text='Hola'), task_id=999, **project_kwargs,
        )

        assert status == 404


class TestListarComentarios:

    def test_devuelve_los_comentarios_en_orden_cronologico(self, call, org_group, project_kwargs, make_task):
        task = make_task(assignees=[org_group.contributor])
        Comment.objects.create(task=task, author=org_group.lead, text='primero')
        Comment.objects.create(task=task, author=org_group.contributor, text='segundo')

        status, data = call(comments, 'get', '/', org_group.contributor, task_id=task.id, **project_kwargs)

        assert status == 200
        assert [c['attributes']['text'] for c in data['data']] == ['primero', 'segundo']

    def test_owner_puede_leer_aunque_no_pueda_comentar(self, call, org_group, project_kwargs, make_task):
        task = make_task()

        status, _data = call(comments, 'get', '/', org_group.owner, task_id=task.id, **project_kwargs)

        assert status == 200

    def test_contributor_no_asignado_no_puede_leer(self, call, org_group, project_kwargs, make_task):
        task = make_task(assignees=[org_group.contributor2])

        status, _data = call(comments, 'get', '/', org_group.contributor, task_id=task.id, **project_kwargs)

        assert status == 403
