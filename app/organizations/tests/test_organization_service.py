import uuid

import pytest
from django.db import IntegrityError

from app.organizations.models import Organization, Membership
from app.organizations.views.organization_view import (
    organizations,
    organization_detail,
    invite_detail,
    invite_regenerate,
    invite_deactivate,
    join,
)

pytestmark = pytest.mark.django_db


def _org_payload(**attrs):
    return {"data": {"type": "organizations", "attributes": attrs}}


class TestCrearOrganizacion:

    def test_asigna_owner_automaticamente(self, call, make_user):
        user = make_user()

        status, data = call(organizations, 'post', '/', user, _org_payload(name='Mi Equipo'))

        assert status == 201
        assert data['data']['attributes']['name'] == 'Mi Equipo'
        assert data['data']['attributes']['role'] == 'owner'
        org_id = data['data']['id']
        assert Membership.objects.get(organization_id=org_id, user=user).role == Membership.Role.OWNER

    def test_defaults_de_plan_y_umbral(self, call, make_user):
        status, data = call(organizations, 'post', '/', make_user(), _org_payload(name='X'))

        attrs = data['data']['attributes']
        assert attrs['plan'] == 'free'
        assert attrs['plan_status'] == 'active'
        assert attrs['overload_threshold'] == 5
        assert attrs['logo_url'] == ''

    def test_sin_name_devuelve_400(self, call, make_user):
        status, data = call(organizations, 'post', '/', make_user(), _org_payload())

        assert status == 400
        assert data['errors'][0]['source']['pointer'] == '/data/attributes/name'

    def test_body_sin_formato_jsonapi_devuelve_400(self, call, make_user):
        status, data = call(organizations, 'post', '/', make_user(), {'name': 'Mi Equipo'})

        assert status == 400


class TestListarOrganizaciones:

    def test_devuelve_solo_las_organizaciones_propias(self, call, make_user, make_organization):
        user = make_user()
        other_user = make_user()
        my_org = make_organization(name='Mi Org')
        other_org = make_organization(name='Org Ajena')
        Membership.objects.create(organization=my_org, user=user, role=Membership.Role.OWNER)
        Membership.objects.create(organization=other_org, user=other_user, role=Membership.Role.OWNER)

        status, data = call(organizations, 'get', '/', user)

        assert status == 200
        names = [item['attributes']['name'] for item in data['data']]
        assert names == ['Mi Org']

    def test_lista_vacia_si_no_pertenece_a_ninguna(self, call, make_user):
        status, data = call(organizations, 'get', '/', make_user())

        assert status == 200
        assert data['data'] == []


class TestObtenerOrganizacion:

    def test_owner_puede_ver_su_organizacion(self, call, owner_org):
        organization, owner = owner_org

        status, data = call(organization_detail, 'get', f'/{organization.id}', owner, organization_id=organization.id)

        assert status == 200
        assert data['data']['attributes']['role'] == 'owner'

    def test_404_si_la_organizacion_no_existe(self, call, make_user):
        status, data = call(organization_detail, 'get', '/999', make_user(), organization_id=999)

        assert status == 404

    def test_403_si_no_es_miembro(self, call, owner_org, make_user):
        organization, _owner = owner_org
        outsider = make_user()

        status, data = call(
            organization_detail, 'get', f'/{organization.id}', outsider, organization_id=organization.id,
        )

        assert status == 403


class TestActualizarOrganizacion:

    def test_owner_puede_renombrar(self, call, owner_org):
        organization, owner = owner_org

        status, data = call(
            organization_detail, 'patch', f'/{organization.id}', owner,
            _org_payload(name='Nuevo nombre'), organization_id=organization.id,
        )

        assert status == 200
        assert data['data']['attributes']['name'] == 'Nuevo nombre'
        organization.refresh_from_db()
        assert organization.name == 'Nuevo nombre'

    def test_owner_puede_cambiar_logo_y_umbral(self, call, owner_org):
        organization, owner = owner_org

        status, data = call(
            organization_detail, 'patch', f'/{organization.id}', owner,
            _org_payload(logo_url='https://cdn.example.com/logo.png', overload_threshold=8),
            organization_id=organization.id,
        )

        assert status == 200
        assert data['data']['attributes']['logo_url'] == 'https://cdn.example.com/logo.png'
        assert data['data']['attributes']['overload_threshold'] == 8

    def test_logo_url_invalida_devuelve_400(self, call, owner_org):
        organization, owner = owner_org

        status, data = call(
            organization_detail, 'patch', f'/{organization.id}', owner,
            _org_payload(logo_url='no-es-una-url'), organization_id=organization.id,
        )

        assert status == 400

    def test_member_no_puede_editar(self, call, owner_org, make_user):
        organization, _owner = owner_org
        member = make_user()
        Membership.objects.create(organization=organization, user=member, role=Membership.Role.MEMBER)

        status, data = call(
            organization_detail, 'patch', f'/{organization.id}', member,
            _org_payload(name='Hackeo'), organization_id=organization.id,
        )

        assert status == 403

    def test_admin_no_puede_editar(self, call, owner_org, make_user):
        organization, _owner = owner_org
        admin = make_user()
        Membership.objects.create(organization=organization, user=admin, role=Membership.Role.ADMIN)

        status, data = call(
            organization_detail, 'patch', f'/{organization.id}', admin,
            _org_payload(name='Hackeo'), organization_id=organization.id,
        )

        assert status == 403


class TestEliminarOrganizacion:

    def test_owner_puede_eliminar(self, call, owner_org):
        organization, owner = owner_org

        status, _data = call(
            organization_detail, 'delete', f'/{organization.id}', owner, organization_id=organization.id,
        )

        assert status == 204
        assert not Organization.objects.filter(id=organization.id).exists()

    def test_admin_no_puede_eliminar(self, call, owner_org, make_user):
        organization, _owner = owner_org
        admin = make_user()
        Membership.objects.create(organization=organization, user=admin, role=Membership.Role.ADMIN)

        status, _data = call(
            organization_detail, 'delete', f'/{organization.id}', admin, organization_id=organization.id,
        )

        assert status == 403
        assert Organization.objects.filter(id=organization.id).exists()


class TestInvitacion:

    def test_owner_ve_el_token(self, call, owner_org):
        organization, owner = owner_org

        status, data = call(invite_detail, 'get', f'/{organization.id}/invite', owner, organization_id=organization.id)

        assert status == 200
        assert data['data']['attributes']['token'] == str(organization.invite_token)
        assert data['data']['attributes']['active'] is True

    def test_admin_tambien_puede_ver_el_token(self, call, owner_org, make_user):
        organization, _owner = owner_org
        admin = make_user()
        Membership.objects.create(organization=organization, user=admin, role=Membership.Role.ADMIN)

        status, _data = call(
            invite_detail, 'get', f'/{organization.id}/invite', admin, organization_id=organization.id,
        )

        assert status == 200

    def test_member_no_puede_ver_el_token(self, call, owner_org, make_user):
        organization, _owner = owner_org
        member = make_user()
        Membership.objects.create(organization=organization, user=member, role=Membership.Role.MEMBER)

        status, _data = call(
            invite_detail, 'get', f'/{organization.id}/invite', member, organization_id=organization.id,
        )

        assert status == 403

    def test_regenerar_cambia_el_token_y_lo_reactiva(self, call, owner_org):
        organization, owner = owner_org
        original_token = organization.invite_token

        status, data = call(
            invite_regenerate, 'post', f'/{organization.id}/invite/regenerate', owner,
            organization_id=organization.id,
        )

        assert status == 200
        assert data['data']['attributes']['token'] != str(original_token)
        assert data['data']['attributes']['active'] is True

    def test_regenerar_requiere_ser_owner(self, call, owner_org, make_user):
        organization, _owner = owner_org
        admin = make_user()
        Membership.objects.create(organization=organization, user=admin, role=Membership.Role.ADMIN)

        status, _data = call(
            invite_regenerate, 'post', f'/{organization.id}/invite/regenerate', admin,
            organization_id=organization.id,
        )

        assert status == 403

    def test_desactivar_token(self, call, owner_org):
        organization, owner = owner_org

        status, data = call(
            invite_deactivate, 'post', f'/{organization.id}/invite/deactivate', owner,
            organization_id=organization.id,
        )

        assert status == 200
        assert data['data']['attributes']['active'] is False


class TestJoin:

    def _join_payload(self, token):
        return {"data": {"type": "invitations", "attributes": {"token": str(token)}}}

    def test_crea_membership_member(self, call, owner_org, make_user):
        organization, _owner = owner_org
        new_user = make_user()

        status, data = call(join, 'post', '/join', new_user, self._join_payload(organization.invite_token))

        assert status == 201
        assert data['data']['attributes']['role'] == 'member'
        assert Membership.objects.get(organization=organization, user=new_user).role == Membership.Role.MEMBER

    def test_token_invalido_devuelve_404(self, call, make_user):
        status, _data = call(join, 'post', '/join', make_user(), self._join_payload('00000000-0000-0000-0000-000000000000'))

        assert status == 404

    @pytest.mark.parametrize('token', ['XX', 'no-es-un-uuid', '1234'])
    def test_token_que_no_es_uuid_da_el_mismo_404_que_uno_inexistente(self, call, make_user, token):
        status, data = call(join, 'post', '/join', make_user(), self._join_payload(token))

        assert status == 404
        assert data['errors'][0]['detail'] == 'Link de invitación inválido o inactivo'

    def test_token_inexistente_tiene_el_mismo_mensaje(self, call, make_user):
        status, data = call(join, 'post', '/join', make_user(), self._join_payload(uuid.uuid4()))

        assert status == 404
        assert data['errors'][0]['detail'] == 'Link de invitación inválido o inactivo'

    def test_token_faltante_da_400_en_espanol(self, call, make_user):
        status, data = call(join, 'post', '/join', make_user(), {"data": {"type": "invitations", "attributes": {}}})

        assert status == 400
        assert data['errors'][0]['detail'] == 'Este campo es requerido.'

    def test_token_desactivado_devuelve_404(self, call, owner_org, make_user):
        organization, _owner = owner_org
        organization.invite_active = False
        organization.save()

        status, _data = call(join, 'post', '/join', make_user(), self._join_payload(organization.invite_token))

        assert status == 404

    def test_ya_es_miembro_devuelve_409(self, call, owner_org):
        organization, owner = owner_org

        status, _data = call(join, 'post', '/join', owner, self._join_payload(organization.invite_token))

        assert status == 409


class TestConstraints:

    def test_unique_owner_per_organization(self, owner_org, make_user):
        organization, _owner = owner_org
        second_user = make_user()

        with pytest.raises(IntegrityError):
            Membership.objects.create(organization=organization, user=second_user, role=Membership.Role.OWNER)

    def test_unique_membership_per_user_per_organization(self, owner_org):
        organization, owner = owner_org

        with pytest.raises(IntegrityError):
            Membership.objects.create(organization=organization, user=owner, role=Membership.Role.MEMBER)
