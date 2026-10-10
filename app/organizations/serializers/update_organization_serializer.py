from rest_framework import serializers


class UpdateOrganizationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    overload_threshold = serializers.IntegerField(min_value=1, required=False)
    logo_url = serializers.URLField(required=False, allow_blank=True)
