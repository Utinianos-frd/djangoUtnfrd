from rest_framework import serializers

from ..models import Task


class UpdateTaskStatusSerializer(serializers.Serializer):
    """Para contributor: solo 'status' (RF-29), nada de título ni asignados."""

    status = serializers.ChoiceField(choices=Task.Status.choices)
