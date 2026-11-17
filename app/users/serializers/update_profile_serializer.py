from rest_framework import serializers


class UpdateProfileSerializer(serializers.Serializer):
    """Valida la edición del perfil (PATCH /auth/me). Todos los campos son opcionales."""

    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, error_messages={'invalid': 'Este campo tiene que ser un texto.'})
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, error_messages={'invalid': 'Este campo tiene que ser un texto.'})
    age = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=150)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, error_messages={'invalid': 'Este campo tiene que ser un texto.'})
    bio = serializers.CharField(max_length=255, required=False, allow_blank=True, error_messages={'invalid': 'Este campo tiene que ser un texto.'})
    avatar_url = serializers.URLField(required=False, allow_blank=True)
