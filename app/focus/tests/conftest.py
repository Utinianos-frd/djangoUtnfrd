from types import SimpleNamespace

import pytest
from app.focus.models import FocusSession
from app.organizations.models import Organization, Group
from app.tasks.models import Project, Task


@pytest.fixture
def make_project(db):
    """Factory de un proyecto en una organización nueva, con el plan indicado."""

    def _make_project(plan=Organization.Plan.PRO, org_name='Pro Org'):
        organization = Organization.objects.create(name=org_name, plan=plan)
        group = Group.objects.create(organization=organization, name='Backend')
        return Project.objects.create(group=group, name='API')

    return _make_project


@pytest.fixture
def focus_user(make_user, make_project):
    """Escenario base: un usuario con dos tareas asignadas en una organización Pro, y otro usuario sin nada.
    Modo Foco no mira roles de organización/grupo — solo asignación de tareas y plan — así que no hacen falta Memberships."""
    user = make_user('focus')
    other = make_user('otro')
    project = make_project()
    task_a = Task.objects.create(project=project, title='Tarea A')
    task_b = Task.objects.create(project=project, title='Tarea B')
    task_a.assignees.set([user])
    task_b.assignees.set([user])
    return SimpleNamespace(user=user, other=other, project=project, task_a=task_a, task_b=task_b)


@pytest.fixture
def active_session(focus_user):
    """Sesión activa de focus_user sobre sus dos tareas."""
    session = FocusSession.objects.create(user=focus_user.user, goal_text='Terminar el login')
    session.tasks.set([focus_user.task_a, focus_user.task_b])
    return session
