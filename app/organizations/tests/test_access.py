import pytest

from app.organizations.access import Access, get_org_and_group
from app.organizations.models import Group, GroupMembership, Membership, Organization
from app.tasks.models import Project, Task

# (rol en la org, rol en el grupo) -> lo que se espera de Access para ese usuario
ROLES = {
    'owner':       (Membership.Role.OWNER, None),
    'admin':       (Membership.Role.ADMIN, None),
    'member':      (Membership.Role.MEMBER, None),
    'lead':        (Membership.Role.MEMBER, GroupMembership.Role.GROUP_LEAD),
    'contributor': (Membership.Role.MEMBER, GroupMembership.Role.CONTRIBUTOR),
    'outsider':    (None, None),
}

#                 is_member is_owner is_overseer is_group_member is_group_lead is_contributor can_view_group can_view_workload sees_all_tasks
EXPECTED = {
    'owner':       (True,  True,  True,  False, False, False, True,  True,  True),
    'admin':       (True,  False, True,  False, False, False, True,  True,  True),
    'member':      (True,  False, False, False, False, False, False, False, False),
    'lead':        (True,  False, False, True,  True,  False, True,  True,  True),
    'contributor': (True,  False, False, True,  False, True,  True,  False, False),
    'outsider':    (False, False, False, False, False, False, False, False, False),
}
PROPS = ('is_member', 'is_owner', 'is_overseer', 'is_group_member', 'is_group_lead', 'is_contributor',
         'can_view_group', 'can_view_workload', 'sees_all_tasks')


@pytest.fixture
def org_group(make_organization):
    organization = make_organization()
    return organization, Group.objects.create(organization=organization, name='G')


def _user_with(make_user, organization, group, name):
    org_role, group_role = ROLES[name]
    user = make_user(name)
    if org_role:
        Membership.objects.create(organization=organization, user=user, role=org_role)
    if group_role:
        GroupMembership.objects.create(group=group, user=user, role=group_role)
    return user


@pytest.mark.parametrize('name', ROLES)
def test_matriz_de_permisos(make_user, org_group, name):
    organization, group = org_group
    access = Access(_user_with(make_user, organization, group, name), organization, group)
    assert tuple(getattr(access, p) for p in PROPS) == EXPECTED[name]


@pytest.mark.parametrize('name, assigned, expected', [
    ('owner', False, True),
    ('lead', False, True),
    ('contributor', False, False),
    ('contributor', True, True),
    ('member', False, False),
])
def test_can_view_task(make_user, org_group, name, assigned, expected):
    organization, group = org_group
    user = _user_with(make_user, organization, group, name)
    task = Task.objects.create(project=Project.objects.create(group=group, name='P'), title='T')
    if assigned:
        task.assignees.add(user)
    access = Access(user, organization, group)
    assert access.is_assigned(task) is assigned
    assert access.can_view_task(task) is expected


def test_sin_organizacion_ni_grupo_no_da_permisos(make_user):
    access = Access(make_user(), None, None)
    assert access.org_role is None and access.group_role is None
    assert not access.is_member and not access.can_view_group


def test_roles_se_consultan_una_sola_vez(make_user, org_group, django_assert_num_queries):
    organization, group = org_group
    access = Access(_user_with(make_user, organization, group, 'lead'), organization, group)
    with django_assert_num_queries(2):  # una para org_role, otra para group_role
        for _ in range(3):
            assert access.can_view_group and access.can_view_workload and access.sees_all_tasks


def test_get_org_and_group(org_group, make_organization):
    organization, group = org_group
    other = make_organization('Otra')
    assert get_org_and_group(organization.id, group.id) == (organization, group)
    assert get_org_and_group(other.id, group.id) == (other, None)  # el grupo no es de esa org
    assert get_org_and_group(999_999, group.id) == (None, None)
    assert Organization.objects.count() == 2
