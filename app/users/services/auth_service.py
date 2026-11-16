from typing import Any
from django.contrib.auth import authenticate
from rest_framework.request import Request
from rest_framework_simplejwt.tokens import RefreshToken
from ..models.users import Users
from ..serializers.register_serializer import RegisterSerializer
from ..serializers.update_profile_serializer import UpdateProfileSerializer
from datetime import datetime, timezone
from app.common.jsonapi import INVALID_BODY, error, extract_attributes, parse_body


def login_usuario(request: Request) -> tuple[dict[str, Any], int]:
    """Autentica username+password y devuelve un par de tokens JWT (access/refresh)."""
    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, INVALID_BODY)

    username = attributes.get('username')
    password = attributes.get('password')

    if not username or not password:
        return error(400, "username y password son requeridos")

    user = authenticate(request, username=username, password=password)

    if not user:
        return error(401, "Credenciales inválidas")

    refresh = RefreshToken.for_user(user)
    return {
        "data": {
            "type": "sessions",
            "attributes": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "exp": datetime.fromtimestamp(refresh.access_token.payload['exp'], tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            },
        }
    }, 200


def register_usuario(request: Request) -> tuple[dict[str, Any], int]:
    """Crea un Users nuevo (username/email únicos) y lo loguea de una, devolviendo tokens JWT."""
    data, err = parse_body(request, RegisterSerializer)
    if err:
        return err

    if Users.objects.filter(username=data['username']).exists():
        return error(409, "El username ya está en uso")

    if Users.objects.filter(email=data['email']).exists():
        return error(409, "El email ya está registrado")

    user = Users.objects.create_user(
        username=data['username'],
        email=data['email'],
        password=data['password'],
        role='user',
    )

    refresh = RefreshToken.for_user(user)
    return {
        "data": {
            "type": "sessions",
            "attributes": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
        }
    }, 201


def get_perfil_usuario(user: Users) -> dict[str, Any]:
    """Serializa el perfil del usuario autenticado para GET /auth/me."""
    return {
        "data": {
            "type": "users",
            "id": str(user.id),
            "attributes": {
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "age": user.age,
                "phone": user.phone,
                "bio": user.bio,
                "avatar_url": user.avatar_url,
            },
            "links": {
                "self": f"/api/v1/auth/me",
            },
        }
    }


def update_perfil_usuario(request: Request) -> tuple[dict[str, Any], int]:
    """Edita el perfil del usuario autenticado (PATCH /auth/me)."""
    body, err = parse_body(request, UpdateProfileSerializer, partial=True)
    if err:
        return err

    user = request.user
    for field, value in body.items():
        setattr(user, field, value)
    user.save()

    return get_perfil_usuario(user), 200
