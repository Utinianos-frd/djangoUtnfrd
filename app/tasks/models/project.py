from django.db import models


class Project(models.Model):
    """Pertenece a un único Group, fijado desde la creación (no hay 'asignar proyecto a grupo' aparte)."""

    group = models.ForeignKey(
        'organizations.Group',
        on_delete=models.CASCADE,
        related_name='projects',
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'projects'

    def __str__(self) -> str:
        return f'{self.name} ({self.group})'
