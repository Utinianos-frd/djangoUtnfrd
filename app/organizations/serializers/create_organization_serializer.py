from rest_framework import serializers


class CreateOrganizationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    logo_url = serializers.URLField(required=False, allow_blank=True)
