from rest_framework import serializers


class CreateGroupSerializer(serializers.Serializer):
    """Valida el body de POST .../groups (crear grupo, solo Owner)."""

    name = serializers.CharField(max_length=255)
