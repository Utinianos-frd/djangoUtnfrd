from rest_framework import serializers


class CreateTaskSerializer(serializers.Serializer):
    """Valida el body de POST .../tasks; assignee_ids es opcional (una tarea puede nacer sin asignar)."""

    title = serializers.CharField(max_length=255)
    assignee_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
