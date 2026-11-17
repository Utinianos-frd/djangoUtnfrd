from rest_framework import serializers


class PomodoroActionSerializer(serializers.Serializer):
    """Acción sobre un pomodoro en curso; la máquina de estados real vive en pomodoro_service.actualizar_pomodoro."""

    action = serializers.ChoiceField(choices=['pause', 'resume', 'cancel', 'complete', 'switch_task'])
    # Solo para 'switch_task': la tarea a la que se pasa el pomodoro en curso.
    task_id = serializers.IntegerField(required=False)

    def validate(self, attrs: dict) -> dict:
        if attrs['action'] == 'switch_task' and attrs.get('task_id') is None:
            raise serializers.ValidationError({'task_id': 'task_id es requerido para cambiar de tarea.'})
        return attrs
