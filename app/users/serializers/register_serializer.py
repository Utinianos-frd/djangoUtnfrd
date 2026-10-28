from rest_framework import serializers

class RegisterSerializer(serializers.Serializer):
    """Valida los datos de alta de un usuario nuevo (POST /auth/register)."""

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
