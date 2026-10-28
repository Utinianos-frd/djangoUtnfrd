import uuid

from django.db import models


class Organization(models.Model):
    """Raíz de la jerarquía Organización → Grupo → Proyecto → Tarea. No tiene un campo 'owner': el dueño es quien tiene una Membership con role='owner'."""

    class Plan(models.TextChoices):
        FREE = 'free', 'Free'
        PRO = 'pro', 'Pro'

    class PlanStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        TRIAL = 'trial', 'Trial'
        EXPIRED = 'expired', 'Expired'

    name = models.CharField(max_length=255)
    logo_url = models.URLField(blank=True, default='')  # solo se valida el formato, no que apunte a una imagen real
    invite_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)  # link de invitación único
    invite_active = models.BooleanField(default=True)  # permite desactivar el link sin borrarlo
    plan = models.CharField(max_length=10, choices=Plan.choices, default=Plan.FREE)
    plan_status = models.CharField(max_length=10, choices=PlanStatus.choices, default=PlanStatus.ACTIVE)
    overload_threshold = models.PositiveIntegerField(default=5)  # umbral de Workload: carga >= esto es 'overloaded'
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'organizations'

    def __str__(self) -> str:
        return self.name
