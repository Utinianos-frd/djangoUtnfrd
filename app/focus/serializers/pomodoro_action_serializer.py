from rest_framework import serializers


class PomodoroActionSerializer(serializers.Serializer):
    """Acción sobre un pomodoro en curso; la máquina de estados real vive en pomodoro_service.actualizar_pomodoro."""

    action = serializers.ChoiceField(choices=['pause', 'resume', 'cancel', 'complete'])
