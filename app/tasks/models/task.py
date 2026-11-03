from django.conf import settings
from django.db import models


class Task(models.Model):
    """Unidad de trabajo dentro de un Project, con cero o más asignados (no un único responsable)."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        IN_PROGRESS = 'in_progress', 'In progress'
        DONE = 'done', 'Done'

    project = models.ForeignKey(
        'tasks.Project',
        on_delete=models.CASCADE,
        related_name='tasks',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    closed_at = models.DateTimeField(null=True, blank=True)  # lo setea el servicio al pasar a DONE; no es editable
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    assignees = models.ManyToManyField(  # una tarea puede tener varios responsables a la vez (RF-26)
        settings.AUTH_USER_MODEL,
        related_name='assigned_tasks',
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tasks'

    def __str__(self) -> str:
        return self.title
