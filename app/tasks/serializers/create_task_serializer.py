from rest_framework import serializers

from ..models import Task


class CreateTaskSerializer(serializers.Serializer):
    """Valida el body de POST .../tasks; assignee_ids es opcional (una tarea puede nacer sin asignar)."""

    title = serializers.CharField(max_length=255, error_messages={'invalid': 'Este campo tiene que ser un texto.'})
    description = serializers.CharField(required=False, allow_blank=True, default='', error_messages={'invalid': 'Este campo tiene que ser un texto.'})
    # Mismos choices que el PATCH. 'blocked' no es un status: se calcula por dependencias, así que no se acepta.
    status = serializers.ChoiceField(choices=Task.Status.choices, required=False, default=Task.Status.PENDING)
    assignee_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
