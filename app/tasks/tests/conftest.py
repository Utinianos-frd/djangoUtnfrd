from types import SimpleNamespace

import pytest
from app.organizations.models import Organization, Membership, Group, GroupMembership
from app.tasks.models import Project, Task


@pytest.fixture
def org_group(make_user):
    """Escenario base de casi todos los tests de esta app: una organización con un usuario por rol
    (owner, admin, member sin grupo, group lead, dos contributors y un outsider sin membresía),
    un grupo y un proyecto dentro de ese grupo."""
    organization = Organization.objects.create(name='Test Org')
    group = Group.objects.create(organization=organization, name='Backend')
    project = Project.objects.create(group=group, name='API')

    users = {
        name: make_user(name)
        for name in ('owner', 'admin', 'member', 'lead', 'contributor', 'contributor2', 'outsider')
    }
    org_roles = {
        'owner': Membership.Role.OWNER,
        'admin': Membership.Role.ADMIN,
        'member': Membership.Role.MEMBER,
        'lead': Membership.Role.MEMBER,
        'contributor': Membership.Role.MEMBER,
        'contributor2': Membership.Role.MEMBER,
    }
    for name, role in org_roles.items():
        Membership.objects.create(organization=organization, user=users[name], role=role)

    GroupMembership.objects.create(group=group, user=users['lead'], role=GroupMembership.Role.GROUP_LEAD)
    for name in ('contributor', 'contributor2'):
        GroupMembership.objects.create(group=group, user=users[name], role=GroupMembership.Role.CONTRIBUTOR)

    return SimpleNamespace(organization=organization, group=group, project=project, **users)


@pytest.fixture
def project_kwargs(org_group):
    """url_kwargs de las vistas anidadas bajo un proyecto (tasks, dependencies)."""
    return {
        'organization_id': org_group.organization.id,
        'group_id': org_group.group.id,
        'project_id': org_group.project.id,
    }


@pytest.fixture
def make_task(org_group):
    """Factory de Task en el proyecto de org_group, con asignados opcionales."""

    def _make_task(title='Tarea', status=Task.Status.PENDING, assignees=(), project=None):
        task = Task.objects.create(project=project or org_group.project, title=title, status=status)
        if assignees:
            task.assignees.set(assignees)
        return task

    return _make_task
