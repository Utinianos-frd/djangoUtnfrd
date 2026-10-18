from rest_framework import serializers


class PomodoroActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['pause', 'resume', 'cancel', 'complete'])
