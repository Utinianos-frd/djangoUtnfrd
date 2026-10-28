from django.db import models


class Group(models.Model):
    """Subdivisión de una Organization. El líder es quien tiene una GroupMembership con role='group_lead' acá, no un campo propio."""

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='groups',
    )
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'groups'

    def __str__(self) -> str:
        return f'{self.name} ({self.organization})'
