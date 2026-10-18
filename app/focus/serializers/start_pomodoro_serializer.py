from rest_framework import serializers


class StartPomodoroSerializer(serializers.Serializer):
    task_id = serializers.IntegerField()
