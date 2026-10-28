from rest_framework import serializers

from ..models import GroupMembership


class UpdateGroupMemberRoleSerializer(serializers.Serializer):
    """Valida el body de PATCH .../groups/{id}/members/{user_id} (asignar group_lead, solo Owner)."""

    role = serializers.ChoiceField(choices=GroupMembership.Role.choices)
