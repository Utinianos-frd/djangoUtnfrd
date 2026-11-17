from rest_framework import serializers


class CreateFocusSessionSerializer(serializers.Serializer):
    """Valida el body de POST /focus-sessions/; task_ids no puede estar vacío (RF-47)."""

    goal_text = serializers.CharField(max_length=200, error_messages={'invalid': 'Este campo tiene que ser un texto.'})
    task_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
