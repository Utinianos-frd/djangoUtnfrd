from datetime import datetime

from django.db import models
from django.utils import timezone


class Pomodoro(models.Model):
    """Un ciclo de 25 min dentro de una FocusSession. El cliente corre el timer; el backend valida transiciones
    y calcula el foco efectivo (para restaurar el timer al recargar y para no aceptar 'complete' antes de tiempo)."""

    DURATION_MINUTES = 25  # fijo por RF-49

    objects: models.Manager['Pomodoro'] = models.Manager()  # explícito: el plugin de django-stubs no lo infiere acá

    class Status(models.TextChoices):
        RUNNING = 'running', 'Running'
        PAUSED = 'paused', 'Paused'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        INTERRUPTED = 'interrupted', 'Interrupted'  # quedó en curso cuando se terminó la sesión

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
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(auto_now_add=True)
    paused_at = models.DateTimeField(null=True, blank=True)  # seteado mientras está pausado, limpio al reanudar
    total_paused_seconds = models.PositiveIntegerField(default=0)  # acumulado a través de ciclos pausar/reanudar
    completed_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)  # cuándo dejó de correr: completed, cancelled o interrupted

    class Meta:
        db_table = 'pomodoros'

    def focus_seconds(self, now: datetime | None = None) -> int:
        """Segundos de foco efectivos (sin pausas), topeados a la duración del pomodoro.
        Corriendo cuenta hasta 'now'; pausado, hasta que se pausó; terminado, hasta ended_at."""
        if self.status == self.Status.PAUSED and self.paused_at:
            end = self.paused_at
        elif self.status == self.Status.RUNNING:
            end = now or timezone.now()
        else:
            # completed_at como respaldo para los completados antes de que existiera ended_at.
            closed_at = self.ended_at or self.completed_at
            if closed_at is None:  # cancelado viejo, sin registro de cuándo terminó
                return 0
            end = closed_at
        seconds = int((end - self.started_at).total_seconds()) - self.total_paused_seconds
        return max(0, min(seconds, self.DURATION_MINUTES * 60))

    def remaining_seconds(self, now: datetime | None = None) -> int:
        """Lo que le falta al timer: duración − foco efectivo (0 si ya se cumplió)."""
        return self.DURATION_MINUTES * 60 - self.focus_seconds(now)

    def __str__(self) -> str:
        return f'Pomodoro #{self.id} ({self.status})'
