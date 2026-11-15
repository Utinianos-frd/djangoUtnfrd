from typing import Any

from app.focus.models import FocusSession, Pomodoro
from app.organizations.models import Organization, Membership, GroupMembership
from app.organizations.services.seed_service import run_seed
from app.organizations.services.workload_service import carga_activa
from app.tasks.models import Project, Task, Comment, TaskDependency
from app.users.models import Users


def _counts() -> dict[str, int]:
    models: list[Any] = [Organization, Users, Membership, GroupMembership, Project, Task,
              TaskDependency, Comment, FocusSession, Pomodoro]
    return {m.__name__: m.objects.count() for m in models}


def test_seed_crea_datos_de_todas_las_entidades(db):
    data = run_seed()

    assert data['summary'] == {
        'users': 8, 'projects': 4, 'tasks': 17, 'dependencies': 8, 'comments': 9, 'focus_sessions': 2,
    }
    assert Organization.objects.get(name='Tasker Demo').plan == Organization.Plan.PRO
    assert Task.objects.filter(status=Task.Status.DONE, closed_at__isnull=True).count() == 0
    assert FocusSession.objects.filter(status=FocusSession.Status.ACTIVE).count() == 1
    # Carga armada a propósito para que el workload muestre los tres estados.
    assert carga_activa(Users.objects.get(username='contributor')) >= 5
    assert carga_activa(Users.objects.get(username='mateo')) == 0


def test_seed_es_idempotente(db):
    run_seed()
    before = _counts()
    run_seed()
    assert _counts() == before


def test_seed_resetea_passwords(db):
    run_seed()
    user = Users.objects.get(username='owner')
    user.set_password('otra')
    user.save()
    run_seed()
    user.refresh_from_db()
    assert user.check_password('owner123')
