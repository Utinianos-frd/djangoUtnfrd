from django.conf import settings
from django.db import models


class GroupMembership(models.Model):
    """El rol de un usuario dentro de un grupo puntual (group_lead/contributor) — un usuario puede tener filas distintas en varios grupos, incluso con roles distintos en cada uno."""

    class Role(models.TextChoices):
        GROUP_LEAD = 'group_lead', 'Group Lead'
        CONTRIBUTOR = 'contributor', 'Contributor'

    group = models.ForeignKey(
        'organizations.Group',
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_memberships',
    )
    role = models.CharField(max_length=11, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'group_memberships'
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'user'],
                name='unique_membership_per_user_per_group',
            ),  # un solo rol por usuario por grupo
            models.UniqueConstraint(
                fields=['group'],
                condition=models.Q(role='group_lead'),
                name='unique_group_lead_per_group',
            ),  # nunca dos group leads a la vez (mismo patrón que unique_owner_per_organization)
        ]

    def __str__(self) -> str:
        return f'{self.user} @ {self.group} ({self.role})'
