from rest_framework import serializers


class UpdateProjectSerializer(serializers.Serializer):
    """Valida el body de PATCH .../projects/{id} (solo owner)."""

    name = serializers.CharField(max_length=255, required=False)
