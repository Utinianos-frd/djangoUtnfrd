from django.db import models


class TaskDependency(models.Model):

    class Type(models.TextChoices):
        FINISH_TO_START = 'FS', 'Finish to Start'
        FINISH_TO_FINISH = 'FF', 'Finish to Finish'

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

    def __str__(self):
        return f'{self.blocking_task_id} -> {self.blocked_task_id} ({self.dependency_type})'
