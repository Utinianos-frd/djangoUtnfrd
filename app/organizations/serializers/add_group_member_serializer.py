from rest_framework import serializers


class AddGroupMemberSerializer(serializers.Serializer):
    """Valida el body de POST .../groups/{id}/members (agregar contributor, solo group lead)."""

    user_id = serializers.IntegerField()
