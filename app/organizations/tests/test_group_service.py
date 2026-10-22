import pytest

from app.organizations.models import Membership, Group, GroupMembership
from app.organizations.views.group_view import groups, group_detail

pytestmark = pytest.mark.django_db


def _group_payload(**attrs):
    return {"data": {"type": "groups", "attributes": attrs}}


class TestCrearGrupo:

    def test_owner_puede_crear_grupo(self, call, owner_org):
        organization, owner = owner_org

        status, data = call(
            groups, 'post', f'/{organization.id}/groups', owner,
            _group_payload(name='Backend'), organization_id=organization.id,
        )

        assert status == 201
        assert data['data']['attributes']['name'] == 'Backend'
        assert data['data']['attributes']['organization_id'] == organization.id

    def test_member_no_puede_crear_grupo(self, call, owner_org, make_user):
        organization, _owner = owner_org
        member = make_user()
        Membership.objects.create(organization=organization, user=member, role=Membership.Role.MEMBER)

        status, _data = call(
            groups, 'post', f'/{organization.id}/groups', member,
            _group_payload(name='Backend'), organization_id=organization.id,
        )

        assert status == 403

    def test_admin_no_puede_crear_grupo(self, call, owner_org, make_user):
        organization, _owner = owner_org
        admin = make_user()
        Membership.objects.create(organization=organization, user=admin, role=Membership.Role.ADMIN)

        status, _data = call(
            groups, 'post', f'/{organization.id}/groups', admin,
            _group_payload(name='Backend'), organization_id=organization.id,
        )

        assert status == 403


class TestListarGrupos:

    def test_owner_ve_todos_los_grupos(self, call, owner_org):
        organization, owner = owner_org
        Group.objects.create(organization=organization, name='Backend')
        Group.objects.create(organization=organization, name='Frontend')

        status, data = call(groups, 'get', f'/{organization.id}/groups', owner, organization_id=organization.id)

        assert status == 200
        assert len(data['data']) == 2

    def test_member_ve_solo_los_grupos_donde_participa(self, call, owner_org, make_user):
        organization, _owner = owner_org
        member = make_user()
        Membership.objects.create(organization=organization, user=member, role=Membership.Role.MEMBER)
        my_group = Group.objects.create(organization=organization, name='Backend')
        Group.objects.create(organization=organization, name='Frontend')
        GroupMembership.objects.create(group=my_group, user=member, role=GroupMembership.Role.CONTRIBUTOR)

        status, data = call(groups, 'get', f'/{organization.id}/groups', member, organization_id=organization.id)

        assert status == 200
        assert [g['attributes']['name'] for g in data['data']] == ['Backend']


class TestGroupDetail:

    def test_owner_puede_editar_nombre(self, call, owner_org):
        organization, owner = owner_org
        group = Group.objects.create(organization=organization, name='Backend')

        status, data = call(
            group_detail, 'patch', f'/{organization.id}/groups/{group.id}', owner,
            _group_payload(name='Core'), organization_id=organization.id, group_id=group.id,
        )

        assert status == 200
        assert data['data']['attributes']['name'] == 'Core'

    def test_member_sin_pertenecer_al_grupo_no_puede_verlo(self, call, owner_org, make_user):
        organization, _owner = owner_org
        group = Group.objects.create(organization=organization, name='Backend')
        member = make_user()
        Membership.objects.create(organization=organization, user=member, role=Membership.Role.MEMBER)

        status, _data = call(
            group_detail, 'get', f'/{organization.id}/groups/{group.id}', member,
            organization_id=organization.id, group_id=group.id,
        )

        assert status == 403

    def test_eliminar_grupo_requiere_ser_owner(self, call, owner_org, make_user):
        organization, _owner = owner_org
        group = Group.objects.create(organization=organization, name='Backend')
        admin = make_user()
        Membership.objects.create(organization=organization, user=admin, role=Membership.Role.ADMIN)

        status, _data = call(
            group_detail, 'delete', f'/{organization.id}/groups/{group.id}', admin,
            organization_id=organization.id, group_id=group.id,
        )

        assert status == 403

    def test_owner_elimina_grupo(self, call, owner_org):
        organization, owner = owner_org
        group = Group.objects.create(organization=organization, name='Backend')

        status, _data = call(
            group_detail, 'delete', f'/{organization.id}/groups/{group.id}', owner,
            organization_id=organization.id, group_id=group.id,
        )

        assert status == 204
        assert not Group.objects.filter(id=group.id).exists()
