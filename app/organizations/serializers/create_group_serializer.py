from rest_framework import serializers


class CreateGroupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
