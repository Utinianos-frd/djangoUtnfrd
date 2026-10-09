from rest_framework import serializers

from ..models import Membership


class UpdateMemberRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Membership.Role.choices)
