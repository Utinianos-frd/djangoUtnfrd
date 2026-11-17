from rest_framework import serializers


class JoinSerializer(serializers.Serializer):
    """Valida el body de POST /organizations/join (unirse vía link de invitación)."""

    # Un token mal formado se trata igual que uno inexistente (ver unirse_a_organizacion).
    token = serializers.UUIDField(error_messages={'invalid': 'Link de invitación inválido o inactivo'})
