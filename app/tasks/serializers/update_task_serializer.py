from rest_framework import serializers

from ..models import Task


class UpdateTaskSerializer(serializers.Serializer):
    """Para el group lead: puede tocar cualquiera de estos campos (ver UpdateTaskStatusSerializer para contributor)."""

    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Task.Status.choices, required=False)
    assignee_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
