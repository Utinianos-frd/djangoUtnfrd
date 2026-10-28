from rest_framework import serializers


class CreateCommentSerializer(serializers.Serializer):
    """Valida el body de POST .../tasks/{id}/comments."""

    text = serializers.CharField()
