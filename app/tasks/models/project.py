from django.db import models


class Project(models.Model):

    group = models.ForeignKey(
        'organizations.Group',
        on_delete=models.CASCADE,
        related_name='projects',
    )
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'projects'

    def __str__(self):
        return f'{self.name} ({self.group})'
