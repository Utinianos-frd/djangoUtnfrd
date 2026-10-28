from rest_framework import serializers

from ..models import TaskDependency


class CreateDependencySerializer(serializers.Serializer):
    """Valida el body de POST .../dependencies; la detección de ciclos pasa en el servicio, no acá."""

    blocking_task_id = serializers.IntegerField()
    blocked_task_id = serializers.IntegerField()
    dependency_type = serializers.ChoiceField(choices=TaskDependency.Type.choices)
