from rest_framework import serializers


class UpdateGroupSerializer(serializers.Serializer):
    """Valida el body de PATCH .../groups/{id} (solo Owner)."""

    name = serializers.CharField(max_length=255, required=False)
