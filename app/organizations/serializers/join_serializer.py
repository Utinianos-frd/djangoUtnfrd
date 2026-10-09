from rest_framework import serializers


class JoinSerializer(serializers.Serializer):
    token = serializers.UUIDField()
