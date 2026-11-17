from rest_framework import serializers


class CreateProjectSerializer(serializers.Serializer):
    """Valida el body de POST .../projects (el group sale de la URL, no del body)."""

    name = serializers.CharField(max_length=255, error_messages={'invalid': 'Este campo tiene que ser un texto.'})
