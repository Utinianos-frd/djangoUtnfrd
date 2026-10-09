from rest_framework import serializers


class UpdateGroupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
