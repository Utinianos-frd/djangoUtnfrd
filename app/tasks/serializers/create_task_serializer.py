from rest_framework import serializers


class CreateTaskSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    assignee_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
