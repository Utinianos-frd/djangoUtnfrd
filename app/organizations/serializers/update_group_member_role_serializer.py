from rest_framework import serializers

from ..models import GroupMembership


class UpdateGroupMemberRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=GroupMembership.Role.choices)
