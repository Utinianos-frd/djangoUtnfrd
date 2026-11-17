from rest_framework import serializers


class CreateCommentSerializer(serializers.Serializer):
    """Valida el body de POST .../tasks/{id}/comments."""

    text = serializers.CharField(
        max_length=2000,
        error_messages={
            'invalid': 'Este campo tiene que ser un texto.',
            'blank': 'El comentario no puede estar vacío.',
            'max_length': 'El comentario no puede superar los 2000 caracteres.',
        },
    )
