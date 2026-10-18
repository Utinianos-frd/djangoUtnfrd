from rest_framework import serializers


class CreateFocusSessionSerializer(serializers.Serializer):
    goal_text = serializers.CharField()
    task_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
