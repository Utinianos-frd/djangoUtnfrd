import uuid

from django.db import models


class Organization(models.Model):

    class Plan(models.TextChoices):
        FREE = 'free', 'Free'
        PRO = 'pro', 'Pro'

    class PlanStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        TRIAL = 'trial', 'Trial'
        EXPIRED = 'expired', 'Expired'

    name = models.CharField(max_length=255)
    logo_url = models.URLField(blank=True, default='')
    invite_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    invite_active = models.BooleanField(default=True)
    plan = models.CharField(max_length=10, choices=Plan.choices, default=Plan.FREE)
    plan_status = models.CharField(max_length=10, choices=PlanStatus.choices, default=PlanStatus.ACTIVE)
    overload_threshold = models.PositiveIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'organizations'

    def __str__(self):
        return self.name
