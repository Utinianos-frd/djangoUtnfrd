from rest_framework import serializers

from ..models import TaskDependency


class CreateDependencySerializer(serializers.Serializer):
    blocking_task_id = serializers.IntegerField()
    blocked_task_id = serializers.IntegerField()
    dependency_type = serializers.ChoiceField(choices=TaskDependency.Type.choices)
