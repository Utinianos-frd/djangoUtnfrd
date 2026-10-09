from django.apps import AppConfig


class TasksConfig(AppConfig):
    name = 'app.tasks'
    label = 'tasks'
    default_auto_field = 'django.db.models.BigAutoField'
