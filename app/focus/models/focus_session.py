from django.conf import settings
from django.db import models


class FocusSession(models.Model):
    """Sesión de Modo Foco de un usuario sobre un set de tareas elegido de antemano (exclusivo plan Pro)."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        ENDED = 'ended', 'Ended'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='focus_sessions',
    )
    goal_text = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    tasks = models.ManyToManyField('tasks.Task', related_name='focus_sessions', blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'focus_sessions'
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(status='active'),
                name='unique_active_focus_session_per_user',
            ),  # nunca dos sesiones activas a la vez para el mismo usuario
        ]

    def __str__(self) -> str:
        return f'{self.user} @ {self.started_at}'
