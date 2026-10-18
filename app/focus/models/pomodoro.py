from django.db import models


class Pomodoro(models.Model):

    DURATION_MINUTES = 25

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
    paused_at = models.DateTimeField(null=True, blank=True)
    total_paused_seconds = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'pomodoros'

    def __str__(self):
        return f'Pomodoro #{self.id} ({self.status})'
