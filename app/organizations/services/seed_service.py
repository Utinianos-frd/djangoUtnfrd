from typing import Any

from app.users.models import Users
from ..models import Organization, Membership, Group, GroupMembership

_ORG_NAME = 'Tasker Demo'
_GROUP_NAME = 'Backend'

_USERS: list[dict[str, str]] = [
    {'username': 'owner', 'org_role': Membership.Role.OWNER},
    {'username': 'admin', 'org_role': Membership.Role.ADMIN},
    {'username': 'member', 'org_role': Membership.Role.MEMBER},
    {'username': 'grouplead', 'org_role': Membership.Role.MEMBER, 'group_role': GroupMembership.Role.GROUP_LEAD},
    {'username': 'contributor', 'org_role': Membership.Role.MEMBER, 'group_role': GroupMembership.Role.CONTRIBUTOR},
]


def _password_for(username: str) -> str:
    """Password determinística por username, así siempre es predecible para el equipo."""
    return f'{username}123'


def _get_or_create_user(username: str) -> Users:
    """Crea el usuario si no existe y siempre resetea su password (idempotente, ver specs/seed-de-datos-de-prueba.md)."""
    user, created = Users.objects.get_or_create(
        username=username,
        defaults={'email': f'{username}@tasker.test', 'role': 'user'},
    )
    user.set_password(_password_for(username))
    user.save()
    return user


def run_seed() -> dict[str, Any]:
    """Crea (o reutiliza) la org/grupo demo con un usuario por cada rol del sistema; solo con DEBUG=True."""
    organization, _ = Organization.objects.get_or_create(name=_ORG_NAME)
    group, _ = Group.objects.get_or_create(organization=organization, name=_GROUP_NAME)

    credentials: list[dict[str, Any]] = []
    for entry in _USERS:
        username = entry['username']
        user = _get_or_create_user(username)

        Membership.objects.get_or_create(
            organization=organization,
            user=user,
            defaults={'role': entry['org_role']},
        )

        group_role = entry.get('group_role')
        if group_role:
            GroupMembership.objects.get_or_create(
                group=group,
                user=user,
                defaults={'role': group_role},
            )

        credentials.append({
            'username': username,
            'password': _password_for(username),
            'org_role': entry['org_role'],
            'group_role': group_role,
        })

    return {
        'organization': organization.name,
        'group': group.name,
        'credentials': credentials,
    }
