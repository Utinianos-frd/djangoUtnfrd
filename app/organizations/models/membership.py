from django.conf import settings
from django.db import models


class Membership(models.Model):

    class Role(models.TextChoices):
        OWNER = 'owner', 'Owner'
        ADMIN = 'admin', 'Admin'
        MEMBER = 'member', 'Member'

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='org_memberships',
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'memberships'
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'user'],
                name='unique_membership_per_user_per_organization',
            ),
            models.UniqueConstraint(
                fields=['organization'],
                condition=models.Q(role='owner'),
                name='unique_owner_per_organization',
            ),
        ]

    def __str__(self):
        return f'{self.user} @ {self.organization} ({self.role})'
