from rest_framework import serializers


class CreateOrganizationSerializer(serializers.Serializer):
    """Valida el body de POST /organizations/ (crear organización)."""

    name = serializers.CharField(max_length=255)
    logo_url = serializers.URLField(required=False, allow_blank=True)
