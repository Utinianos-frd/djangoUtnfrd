from typing import Any
from django.contrib.auth import authenticate
from rest_framework.request import Request
from rest_framework_simplejwt.tokens import RefreshToken
from ..models.users import Users
from ..serializers.register_serializer import RegisterSerializer
from datetime import datetime, timezone


def _error(status_code: int, detail: str) -> tuple[dict[str, Any], int]:
    """Arma un error en formato JSON:API: { errors: [{ status, detail }] }."""
    return {"errors": [{"status": str(status_code), "detail": detail}]}, status_code


def _extract_attributes(request: Request) -> dict[str, Any] | None:
    """Saca request.data['data']['attributes'] del body JSON:API, o None si no tiene esa forma."""
    try:
        return request.data['data']['attributes']
    except (KeyError, TypeError):
        return None


def login_usuario(request: Request) -> tuple[dict[str, Any], int]:
    """Autentica username+password y devuelve un par de tokens JWT (access/refresh)."""
    attributes = _extract_attributes(request)
    if attributes is None:
        return _error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    username = attributes.get('username')
    password = attributes.get('password')

    if not username or not password:
        return _error(400, "username y password son requeridos")

    user = authenticate(request, username=username, password=password)

    if not user:
        return _error(401, "Credenciales inválidas")

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
    attributes = _extract_attributes(request)
    if attributes is None:
        return _error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = RegisterSerializer(data=attributes)
    if not serializer.is_valid():
        errors = [
            {"status": "400", "source": {"pointer": f"/data/attributes/{field}"}, "detail": str(msgs[0])}
            for field, msgs in serializer.errors.items()
        ]
        return {"errors": errors}, 400

    data = serializer.validated_data

    if Users.objects.filter(username=data['username']).exists():
        return _error(409, "El username ya está en uso")

    if Users.objects.filter(email=data['email']).exists():
        return _error(409, "El email ya está registrado")

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
            },
            "links": {
                "self": f"/api/v1/auth/me",
            },
        }
    }
