import pytest
from app.organizations.models import Organization, Membership


@pytest.fixture
def make_organization(db):
    """Factory de Organization. No crea ninguna Membership — para eso usar owner_org o crearla a mano."""

    def _make_organization(name='Test Org', **extra):
        return Organization.objects.create(name=name, **extra)

    return _make_organization


@pytest.fixture
def owner_org(make_user, make_organization):
    """Una organización con su owner ya asignado — el punto de partida típico para testear
    cualquier cosa que dependa de 'ya existe una org con alguien al mando'."""
    owner = make_user('owner')
    organization = make_organization()
    Membership.objects.create(organization=organization, user=owner, role=Membership.Role.OWNER)
    return organization, owner
