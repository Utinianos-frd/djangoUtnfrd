from rest_framework import serializers


class JoinSerializer(serializers.Serializer):
    """Valida el body de POST /organizations/join (unirse vía link de invitación)."""

    token = serializers.UUIDField()
