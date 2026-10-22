import pytest

from app.organizations.models import Membership
from app.organizations.views.membership_view import members, member_detail

pytestmark = pytest.mark.django_db


def _role_payload(role):
    return {"data": {"type": "memberships", "attributes": {"role": role}}}


class TestListarMiembros:

    def test_cualquier_miembro_puede_listar(self, call, owner_org, make_user):
        organization, owner = owner_org
        plain_member = make_user()
        Membership.objects.create(organization=organization, user=plain_member, role=Membership.Role.MEMBER)

        status, data = call(members, 'get', f'/{organization.id}/members', plain_member, organization_id=organization.id)

        assert status == 200
        usernames = {m['attributes']['username'] for m in data['data']}
        assert usernames == {owner.username, plain_member.username}

    def test_outsider_no_puede_listar(self, call, owner_org, make_user):
        organization, _owner = owner_org

        status, _data = call(
            members, 'get', f'/{organization.id}/members', make_user(), organization_id=organization.id,
        )

        assert status == 403


class TestCambiarRolMiembro:

    def test_owner_puede_promover_a_admin(self, call, owner_org, make_user):
        organization, owner = owner_org
        member = make_user()
        Membership.objects.create(organization=organization, user=member, role=Membership.Role.MEMBER)

        status, data = call(
            member_detail, 'patch', f'/{organization.id}/members/{member.id}', owner,
            _role_payload('admin'), organization_id=organization.id, user_id=member.id,
        )

        assert status == 200
        assert data['data']['attributes']['role'] == 'admin'

    def test_admin_no_puede_cambiar_roles(self, call, owner_org, make_user):
        organization, _owner = owner_org
        admin = make_user()
        target = make_user()
        Membership.objects.create(organization=organization, user=admin, role=Membership.Role.ADMIN)
        Membership.objects.create(organization=organization, user=target, role=Membership.Role.MEMBER)

        status, _data = call(
            member_detail, 'patch', f'/{organization.id}/members/{target.id}', admin,
            _role_payload('admin'), organization_id=organization.id, user_id=target.id,
        )

        assert status == 403

    def test_traspasar_ownership_demueve_al_owner_anterior_a_admin(self, call, owner_org, make_user):
        organization, owner = owner_org
        successor = make_user()
        Membership.objects.create(organization=organization, user=successor, role=Membership.Role.MEMBER)

        status, data = call(
            member_detail, 'patch', f'/{organization.id}/members/{successor.id}', owner,
            _role_payload('owner'), organization_id=organization.id, user_id=successor.id,
        )

        assert status == 200
        assert data['data']['attributes']['role'] == 'owner'
        assert Membership.objects.get(organization=organization, user=owner).role == Membership.Role.ADMIN
        assert Membership.objects.filter(organization=organization, role=Membership.Role.OWNER).count() == 1

    def test_no_se_puede_bajar_al_owner_directamente(self, call, owner_org):
        organization, owner = owner_org

        status, data = call(
            member_detail, 'patch', f'/{organization.id}/members/{owner.id}', owner,
            _role_payload('admin'), organization_id=organization.id, user_id=owner.id,
        )

        assert status == 400
        assert Membership.objects.get(organization=organization, user=owner).role == Membership.Role.OWNER

    def test_404_si_el_usuario_no_pertenece_a_la_organizacion(self, call, owner_org, make_user):
        organization, owner = owner_org
        outsider = make_user()

        status, _data = call(
            member_detail, 'patch', f'/{organization.id}/members/{outsider.id}', owner,
            _role_payload('admin'), organization_id=organization.id, user_id=outsider.id,
        )

        assert status == 404


class TestEliminarMiembro:

    def test_owner_puede_eliminar_a_un_member(self, call, owner_org, make_user):
        organization, owner = owner_org
        member = make_user()
        Membership.objects.create(organization=organization, user=member, role=Membership.Role.MEMBER)

        status, _data = call(
            member_detail, 'delete', f'/{organization.id}/members/{member.id}', owner,
            organization_id=organization.id, user_id=member.id,
        )

        assert status == 204
        assert not Membership.objects.filter(organization=organization, user=member).exists()

    def test_admin_tambien_puede_eliminar_miembros(self, call, owner_org, make_user):
        organization, _owner = owner_org
        admin = make_user()
        member = make_user()
        Membership.objects.create(organization=organization, user=admin, role=Membership.Role.ADMIN)
        Membership.objects.create(organization=organization, user=member, role=Membership.Role.MEMBER)

        status, _data = call(
            member_detail, 'delete', f'/{organization.id}/members/{member.id}', admin,
            organization_id=organization.id, user_id=member.id,
        )

        assert status == 204

    def test_member_no_puede_eliminar_a_nadie(self, call, owner_org, make_user):
        organization, _owner = owner_org
        member = make_user()
        other = make_user()
        Membership.objects.create(organization=organization, user=member, role=Membership.Role.MEMBER)
        Membership.objects.create(organization=organization, user=other, role=Membership.Role.MEMBER)

        status, _data = call(
            member_detail, 'delete', f'/{organization.id}/members/{other.id}', member,
            organization_id=organization.id, user_id=other.id,
        )

        assert status == 403

    def test_no_se_puede_eliminar_al_owner(self, call, owner_org):
        organization, owner = owner_org

        status, _data = call(
            member_detail, 'delete', f'/{organization.id}/members/{owner.id}', owner,
            organization_id=organization.id, user_id=owner.id,
        )

        assert status == 400
        assert Membership.objects.filter(organization=organization, user=owner).exists()
