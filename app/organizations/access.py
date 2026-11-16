"""Política de acceso: un único lugar para responder "¿qué puede hacer este usuario acá?".

Uso típico en un servicio:

    organization, group = get_org_and_group(organization_id, group_id)
    ...
    access = Access(user, organization, group)
    if not access.can_view_group:
        return error(403, "...")

Los roles se consultan a la base una sola vez por instancia (cached_property), así que preguntar
varias cosas sobre el mismo Access no repite queries.
"""
from functools import cached_property
from typing import TYPE_CHECKING

from app.users.models import Users
from .models import Organization, Group, Membership, GroupMembership

if TYPE_CHECKING:
    from app.tasks.models import Task


def get_org_and_group(organization_id: int, group_id: int) -> tuple[Organization | None, Group | None]:
    """Resuelve (organization, group) por id: (None, None) si no existe la org, (org, None) si no existe el grupo en ella."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return None, None
    group = Group.objects.filter(id=group_id, organization=organization).first()
    return organization, group


class Access:
    """Roles de un usuario en una organización (y opcionalmente en uno de sus grupos)."""

    def __init__(self, user: Users, organization: Organization | None, group: Group | None = None) -> None:
        self.user = user
        self.organization = organization
        self.group = group

    # --- Roles ---------------------------------------------------------------------------------

    @cached_property
    def org_role(self) -> str | None:
        """owner/admin/member en esta organización, o None si no es miembro."""
        if self.organization is None:
            return None
        membership = Membership.objects.filter(organization=self.organization, user=self.user).first()
        return membership.role if membership else None

    @cached_property
    def group_role(self) -> str | None:
        """group_lead/contributor en este grupo, o None si no pertenece (o no se indicó grupo)."""
        if self.group is None:
            return None
        membership = GroupMembership.objects.filter(group=self.group, user=self.user).first()
        return membership.role if membership else None

    # --- Organización --------------------------------------------------------------------------

    @property
    def is_member(self) -> bool:
        """Pertenece a la organización, con cualquier rol."""
        return self.org_role is not None

    @property
    def is_owner(self) -> bool:
        return self.org_role == Membership.Role.OWNER

    @property
    def is_overseer(self) -> bool:
        """Owner o admin: visibilidad total sobre la organización (no necesariamente edición)."""
        return self.org_role in (Membership.Role.OWNER, Membership.Role.ADMIN)

    # --- Grupo ---------------------------------------------------------------------------------

    @property
    def is_group_member(self) -> bool:
        """Pertenece al grupo, como group lead o contributor."""
        return self.group_role is not None

    @property
    def is_group_lead(self) -> bool:
        return self.group_role == GroupMembership.Role.GROUP_LEAD

    @property
    def is_contributor(self) -> bool:
        return self.group_role == GroupMembership.Role.CONTRIBUTOR

    @property
    def can_view_group(self) -> bool:
        """Owner/admin ven cualquier grupo; el resto solo si pertenece a él (también aplica a sus proyectos y miembros)."""
        return self.is_overseer or self.is_group_member

    @property
    def can_view_workload(self) -> bool:
        """Owner/admin, o el group lead de este grupo (RF-39)."""
        return self.is_overseer or self.is_group_lead

    @property
    def sees_all_tasks(self) -> bool:
        """Owner/admin/group lead ven todas las tareas y dependencias del grupo; un contributor solo las suyas."""
        return self.is_overseer or self.is_group_lead

    # --- Tareas --------------------------------------------------------------------------------

    def is_assigned(self, task: 'Task') -> bool:
        """Figura como asignado. Ojo: por sí solo no da permisos, usar is_active_assignee."""
        return task.assignees.filter(id=self.user.id).exists()

    def is_active_assignee(self, task: 'Task') -> bool:
        """Asignado a la tarea Y todavía miembro del grupo: una asignación vieja de alguien que ya salió no da acceso."""
        return self.is_group_member and self.is_assigned(task)

    def can_view_task(self, task: 'Task') -> bool:
        """Owner/admin/group lead ven cualquiera; el resto solo si es asignado activo de esta tarea."""
        return self.sees_all_tasks or self.is_active_assignee(task)
