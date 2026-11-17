from rest_framework import serializers


class UpdateProjectSerializer(serializers.Serializer):
    """Valida el body de PATCH .../projects/{id} (solo owner)."""

    name = serializers.CharField(max_length=255, required=False, error_messages={'invalid': 'Este campo tiene que ser un texto.'})
