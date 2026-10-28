from django.conf import settings
from django.db import models


class Comment(models.Model):
    """Comentario de un usuario sobre una tarea puntual (RF-30); sin edición ni borrado todavía."""

    objects: models.Manager['Comment'] = models.Manager()  # explícito: el plugin de django-stubs no lo infiere acá

    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='comments',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='task_comments',
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'task_comments'
        ordering = ['created_at']

    def __str__(self) -> str:
        return f'{self.author} @ {self.task}'
