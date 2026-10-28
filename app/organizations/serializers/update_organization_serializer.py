from rest_framework import serializers


class UpdateOrganizationSerializer(serializers.Serializer):
    """Valida el body de PATCH /organizations/{id} — todos los campos opcionales (partial update)."""

    name = serializers.CharField(max_length=255, required=False)
    overload_threshold = serializers.IntegerField(min_value=1, required=False)
    logo_url = serializers.URLField(required=False, allow_blank=True)
