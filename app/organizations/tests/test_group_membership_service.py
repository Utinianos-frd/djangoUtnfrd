import pytest

from app.organizations.models import Membership, Group, GroupMembership
from app.organizations.views.group_membership_view import group_members, group_member_detail

pytestmark = pytest.mark.django_db


@pytest.fixture
def group(owner_org):
    organization, _owner = owner_org
    return Group.objects.create(organization=organization, name='Backend')


def _role_payload(role):
    return {"data": {"type": "group_memberships", "attributes": {"role": role}}}


def _member_payload(user_id):
    return {"data": {"type": "group_memberships", "attributes": {"user_id": user_id}}}


class TestBootstrapDelGroupLead:
    """El escenario que expuso el bug real: nadie podía llegar a ser el primer group lead de un
    grupo nuevo, porque agregar miembros exigía ya ser group lead y asignar el rol exigía que la
    membership ya existiera. Ver specs/grupos_y_roles/grupos-abm.md §3."""

    def test_owner_puede_asignar_group_lead_sin_membership_previa(self, call, owner_org, group, make_user):
        organization, owner = owner_org
        candidate = make_user()
        Membership.objects.create(organization=organization, user=candidate, role=Membership.Role.MEMBER)
        assert not GroupMembership.objects.filter(group=group, user=candidate).exists()

        status, data = call(
            group_member_detail, 'patch', f'/{organization.id}/groups/{group.id}/members/{candidate.id}', owner,
            _role_payload('group_lead'), organization_id=organization.id, group_id=group.id, user_id=candidate.id,
        )

        assert status == 200
        assert data['data']['attributes']['role'] == 'group_lead'
        assert GroupMembership.objects.get(group=group, user=candidate).role == GroupMembership.Role.GROUP_LEAD

    def test_despues_del_bootstrap_el_group_lead_puede_agregar_miembros(self, call, owner_org, group, make_user):
        organization, owner = owner_org
        lead = make_user()
        contributor = make_user()
        Membership.objects.create(organization=organization, user=lead, role=Membership.Role.MEMBER)
        Membership.objects.create(organization=organization, user=contributor, role=Membership.Role.MEMBER)
        call(
            group_member_detail, 'patch', f'/{organization.id}/groups/{group.id}/members/{lead.id}', owner,
            _role_payload('group_lead'), organization_id=organization.id, group_id=group.id, user_id=lead.id,
        )

        status, data = call(
            group_members, 'post', f'/{organization.id}/groups/{group.id}/members', lead,
            _member_payload(contributor.id), organization_id=organization.id, group_id=group.id,
        )

        assert status == 201
        assert data['data']['attributes']['role'] == 'contributor'

    def test_owner_bootstrap_requiere_que_el_candidato_sea_member_de_la_org(self, call, owner_org, group, make_user):
        organization, owner = owner_org
        outsider = make_user()  # no tiene Membership en esta organización

        status, _data = call(
            group_member_detail, 'patch', f'/{organization.id}/groups/{group.id}/members/{outsider.id}', owner,
            _role_payload('group_lead'), organization_id=organization.id, group_id=group.id, user_id=outsider.id,
        )

        assert status == 400


class TestAgregarMiembroGrupo:

    def _make_lead(self, organization, group, make_user):
        lead = make_user()
        Membership.objects.create(organization=organization, user=lead, role=Membership.Role.MEMBER)
        GroupMembership.objects.create(group=group, user=lead, role=GroupMembership.Role.GROUP_LEAD)
        return lead

    def test_requiere_ser_org_member_antes_de_sumarlo_al_grupo(self, call, owner_org, group, make_user):
        organization, _owner = owner_org
        lead = self._make_lead(organization, group, make_user)
        outsider = make_user()  # no es Member de la organización

        status, _data = call(
            group_members, 'post', f'/{organization.id}/groups/{group.id}/members', lead,
            _member_payload(outsider.id), organization_id=organization.id, group_id=group.id,
        )

        assert status == 400
        assert not GroupMembership.objects.filter(group=group, user=outsider).exists()

    def test_no_se_puede_duplicar_la_membership(self, call, owner_org, group, make_user):
        organization, _owner = owner_org
        lead = self._make_lead(organization, group, make_user)

        status, _data = call(
            group_members, 'post', f'/{organization.id}/groups/{group.id}/members', lead,
            _member_payload(lead.id), organization_id=organization.id, group_id=group.id,
        )

        assert status == 409

    def test_contributor_no_puede_agregar_miembros(self, call, owner_org, group, make_user):
        organization, _owner = owner_org
        contributor = make_user()
        other = make_user()
        Membership.objects.create(organization=organization, user=contributor, role=Membership.Role.MEMBER)
        Membership.objects.create(organization=organization, user=other, role=Membership.Role.MEMBER)
        GroupMembership.objects.create(group=group, user=contributor, role=GroupMembership.Role.CONTRIBUTOR)

        status, _data = call(
            group_members, 'post', f'/{organization.id}/groups/{group.id}/members', contributor,
            _member_payload(other.id), organization_id=organization.id, group_id=group.id,
        )

        assert status == 403


class TestTraspasoDeGroupLead:

    def test_asignar_nuevo_group_lead_demueve_al_anterior_a_contributor(self, call, owner_org, group, make_user):
        organization, owner = owner_org
        old_lead = make_user()
        new_lead = make_user()
        Membership.objects.create(organization=organization, user=old_lead, role=Membership.Role.MEMBER)
        Membership.objects.create(organization=organization, user=new_lead, role=Membership.Role.MEMBER)
        GroupMembership.objects.create(group=group, user=old_lead, role=GroupMembership.Role.GROUP_LEAD)

        status, data = call(
            group_member_detail, 'patch', f'/{organization.id}/groups/{group.id}/members/{new_lead.id}', owner,
            _role_payload('group_lead'), organization_id=organization.id, group_id=group.id, user_id=new_lead.id,
        )

        assert status == 200
        assert GroupMembership.objects.get(group=group, user=old_lead).role == GroupMembership.Role.CONTRIBUTOR
        assert GroupMembership.objects.filter(group=group, role=GroupMembership.Role.GROUP_LEAD).count() == 1

    def test_no_se_puede_bajar_al_group_lead_directamente(self, call, owner_org, group, make_user):
        organization, owner = owner_org
        lead = make_user()
        Membership.objects.create(organization=organization, user=lead, role=Membership.Role.MEMBER)
        GroupMembership.objects.create(group=group, user=lead, role=GroupMembership.Role.GROUP_LEAD)

        status, _data = call(
            group_member_detail, 'patch', f'/{organization.id}/groups/{group.id}/members/{lead.id}', owner,
            _role_payload('contributor'), organization_id=organization.id, group_id=group.id, user_id=lead.id,
        )

        assert status == 400
        assert GroupMembership.objects.get(group=group, user=lead).role == GroupMembership.Role.GROUP_LEAD


class TestEliminarMiembroGrupo:

    def test_group_lead_elimina_a_un_contributor(self, call, owner_org, group, make_user):
        organization, _owner = owner_org
        lead = make_user()
        contributor = make_user()
        Membership.objects.create(organization=organization, user=lead, role=Membership.Role.MEMBER)
        Membership.objects.create(organization=organization, user=contributor, role=Membership.Role.MEMBER)
        GroupMembership.objects.create(group=group, user=lead, role=GroupMembership.Role.GROUP_LEAD)
        GroupMembership.objects.create(group=group, user=contributor, role=GroupMembership.Role.CONTRIBUTOR)

        status, _data = call(
            group_member_detail, 'delete', f'/{organization.id}/groups/{group.id}/members/{contributor.id}', lead,
            organization_id=organization.id, group_id=group.id, user_id=contributor.id,
        )

        assert status == 204
        assert not GroupMembership.objects.filter(group=group, user=contributor).exists()

    def test_no_se_puede_eliminar_al_group_lead(self, call, owner_org, group, make_user):
        organization, _owner = owner_org
        lead = make_user()
        Membership.objects.create(organization=organization, user=lead, role=Membership.Role.MEMBER)
        GroupMembership.objects.create(group=group, user=lead, role=GroupMembership.Role.GROUP_LEAD)

        status, _data = call(
            group_member_detail, 'delete', f'/{organization.id}/groups/{group.id}/members/{lead.id}', lead,
            organization_id=organization.id, group_id=group.id, user_id=lead.id,
        )

        assert status == 400
        assert GroupMembership.objects.filter(group=group, user=lead).exists()

    def test_owner_no_puede_eliminar_miembros_de_grupo_directamente(self, call, owner_org, group, make_user):
        """A diferencia de eliminar miembros de la organización (donde Owner y Admin pueden), a nivel
        de grupo la matriz del documento solo lista al Group Lead — ver grupos-abm.md."""
        organization, owner = owner_org
        contributor = make_user()
        Membership.objects.create(organization=organization, user=contributor, role=Membership.Role.MEMBER)
        GroupMembership.objects.create(group=group, user=contributor, role=GroupMembership.Role.CONTRIBUTOR)

        status, _data = call(
            group_member_detail, 'delete', f'/{organization.id}/groups/{group.id}/members/{contributor.id}', owner,
            organization_id=organization.id, group_id=group.id, user_id=contributor.id,
        )

        assert status == 403
