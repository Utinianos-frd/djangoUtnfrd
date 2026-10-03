from django.conf import settings
from django.db import models


class GroupMembership(models.Model):

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
            ),
            models.UniqueConstraint(
                fields=['group'],
                condition=models.Q(role='group_lead'),
                name='unique_group_lead_per_group',
            ),
        ]

    def __str__(self):
        return f'{self.user} @ {self.group} ({self.role})'
