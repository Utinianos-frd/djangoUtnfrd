from django.db import models
from django.contrib.auth.models import AbstractBaseUser, AbstractUser, BaseUserManager

class Users(AbstractUser):
    """Cuenta de usuario del sistema. El rol de negocio (owner/admin/member, etc.) NO vive acá, sino en Membership/GroupMembership por organización."""

    username = models.CharField(max_length=255,unique=True)
    password = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=50)  # genérico, siempre 'user' hoy; no confundir con el rol de organización/grupo
    # Datos de perfil (first_name/last_name vienen de AbstractUser).
    age = models.PositiveIntegerField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True, default='')
    bio = models.CharField(max_length=255, blank=True, default='')
    avatar_url = models.URLField(blank=True, default='')

    class Meta:
        db_table = 'users'

    def __str__(self) -> str:
        return self.username