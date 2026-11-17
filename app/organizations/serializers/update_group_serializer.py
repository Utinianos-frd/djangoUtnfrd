from rest_framework import serializers


class UpdateGroupSerializer(serializers.Serializer):
    """Valida el body de PATCH .../groups/{id} (solo Owner)."""

    name = serializers.CharField(max_length=255, required=False, error_messages={'invalid': 'Este campo tiene que ser un texto.'})
