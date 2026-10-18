from django.conf import settings
from django.db import models


class Comment(models.Model):

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

    def __str__(self):
        return f'{self.author} @ {self.task}'
