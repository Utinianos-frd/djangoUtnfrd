from rest_framework import serializers

from ..models import Task


class UpdateTaskStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Task.Status.choices)
