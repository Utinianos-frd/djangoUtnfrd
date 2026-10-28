from django.db import models


class Pomodoro(models.Model):
    """Un ciclo de 25 min dentro de una FocusSession. El backend valida transiciones de estado, no mide el tiempo real."""

    DURATION_MINUTES = 25  # fijo por RF-49; el cliente corre el timer, el backend solo valida estados

    objects: models.Manager['Pomodoro'] = models.Manager()  # explícito: el plugin de django-stubs no lo infiere acá

    class Status(models.TextChoices):
        RUNNING = 'running', 'Running'
        PAUSED = 'paused', 'Paused'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    session = models.ForeignKey(
        'focus.FocusSession',
        on_delete=models.CASCADE,
        related_name='pomodoros',
    )
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='pomodoros',
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(auto_now_add=True)
    paused_at = models.DateTimeField(null=True, blank=True)  # seteado mientras está pausado, limpio al reanudar
    total_paused_seconds = models.PositiveIntegerField(default=0)  # acumulado a través de ciclos pausar/reanudar
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'pomodoros'

    def __str__(self) -> str:
        return f'Pomodoro #{self.id} ({self.status})'
