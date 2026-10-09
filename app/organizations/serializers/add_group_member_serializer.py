from rest_framework import serializers


class AddGroupMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
