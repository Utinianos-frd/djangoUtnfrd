from rest_framework import serializers

from ..models import Task


class UpdateTaskSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    status = serializers.ChoiceField(choices=Task.Status.choices, required=False)
    assignee_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
