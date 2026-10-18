from rest_framework import serializers


class CreateCommentSerializer(serializers.Serializer):
    text = serializers.CharField()
