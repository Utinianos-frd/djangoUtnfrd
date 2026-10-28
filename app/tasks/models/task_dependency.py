from django.db import models


class TaskDependency(models.Model):
    """blocking_task tiene que completarse antes de que blocked_task pueda avanzar (FS) o completarse (FF)."""

    class Type(models.TextChoices):
        FINISH_TO_START = 'FS', 'Finish to Start'  # blocked no puede salir de 'pending' hasta que blocking esté 'done'
        FINISH_TO_FINISH = 'FF', 'Finish to Finish'  # blocked no puede llegar a 'done' hasta que blocking esté 'done'

    blocking_task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='blocks',
    )
    blocked_task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='blocked_by',
    )
    dependency_type = models.CharField(max_length=2, choices=Type.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'task_dependencies'
        constraints = [
            models.UniqueConstraint(
                fields=['blocking_task', 'blocked_task'],
                name='unique_dependency_per_task_pair',
            ),
            models.CheckConstraint(
                check=~models.Q(blocking_task=models.F('blocked_task')),
                name='no_self_dependency',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.blocking_task_id} -> {self.blocked_task_id} ({self.dependency_type})'
