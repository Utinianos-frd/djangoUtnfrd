from rest_framework import serializers


class StartPomodoroSerializer(serializers.Serializer):
    """task_id tiene que ser una de las tareas elegidas al iniciar la sesión (se valida en el servicio)."""

    task_id = serializers.IntegerField()
