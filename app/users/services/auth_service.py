from typing import Any, cast
import requests
from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework.request import Request
from rest_framework_simplejwt.tokens import RefreshToken
from ..models.users import Users
from ..serializers.register_serializer import RegisterSerializer
from ..serializers.update_profile_serializer import UpdateProfileSerializer
from datetime import datetime, timezone


# Endpoint oficial de Google que valida la firma y la expiración de un ID token y
# devuelve sus claims. Lo usamos en vez de la librería google-auth para no sumar
# dependencias: `requests` ya está instalado.
_GOOGLE_TOKENINFO_URL = 'https://oauth2.googleapis.com/tokeninfo'
_GOOGLE_VALID_ISSUERS = {'accounts.google.com', 'https://accounts.google.com'}


def _error(status_code: int, detail: str) -> tuple[dict[str, Any], int]:
    """Arma un error en formato JSON:API: { errors: [{ status, detail }] }."""
    return {"errors": [{"status": str(status_code), "detail": detail}]}, status_code


def _extract_attributes(request: Request) -> dict[str, Any] | None:
    """Saca request.data['data']['attributes'] del body JSON:API, o None si no tiene esa forma."""
    try:
        return request.data['data']['attributes']
    except (KeyError, TypeError):
        return None


def _tokens_para(user: Users, status_code: int = 200) -> tuple[dict[str, Any], int]:
    """Emite el par access/refresh para `user`, en el mismo formato JSON:API que usa el login."""
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
    }, status_code


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


def _verificar_id_token_google(id_token: str) -> dict[str, Any] | None:
    """
    Valida un ID token de Google contra el endpoint oficial de tokeninfo y devuelve sus
    claims si es legítimo (firma válida, no expirado, emitido por Google y para NUESTRA app),
    o None si no lo es.
    """
    try:
        resp = requests.get(_GOOGLE_TOKENINFO_URL, params={'id_token': id_token}, timeout=10)
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    claims = resp.json()

    # El token tiene que haber sido emitido para nuestra app (aud) por Google (iss),
    # y el mail tiene que estar verificado.
    if claims.get('aud') != settings.GOOGLE_CLIENT_ID:
        return None
    if claims.get('iss') not in _GOOGLE_VALID_ISSUERS:
        return None
    if str(claims.get('email_verified', 'false')).lower() != 'true':
        return None
    if not claims.get('email'):
        return None

    return claims


def _username_libre(base: str) -> str:
    """Deriva un username único a partir de `base` (p. ej. el local part del mail)."""
    base = ''.join(c for c in base if c.isalnum() or c in '._-') or 'user'
    base = base[:150]
    candidate = base
    i = 0
    while Users.objects.filter(username=candidate).exists():
        i += 1
        candidate = f'{base}{i}'
    return candidate


def google_login_usuario(request: Request) -> tuple[dict[str, Any], int]:
    """
    Login/registro con Google (POST /auth/google).

    Recibe en los attributes un `id_token` emitido por Google Identity Services en el
    frontend, lo valida, y busca o crea el Users asociado a ese email. Devuelve el mismo
    par de tokens JWT que el login normal, así el frontend no distingue el origen.
    """
    if not settings.GOOGLE_CLIENT_ID:
        return _error(503, "El login con Google no está configurado en el servidor (falta GOOGLE_CLIENT_ID)")

    attributes = _extract_attributes(request)
    if attributes is None:
        return _error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    id_token = attributes.get('id_token') or attributes.get('credential')
    if not id_token:
        return _error(400, "Falta el id_token de Google")

    claims = _verificar_id_token_google(id_token)
    if claims is None:
        return _error(401, "El token de Google no es válido")

    email = claims['email']
    user = Users.objects.filter(email=email).first()

    if user is None:
        # Primera vez con Google: creamos la cuenta. Sin contraseña usable (solo entra por Google).
        username = _username_libre(claims.get('email', '').split('@')[0])
        user = Users.objects.create_user(
            username=username,
            email=email,
            password=None,
            role='user',
            first_name=claims.get('given_name', '') or '',
            last_name=claims.get('family_name', '') or '',
        )
        user.set_unusable_password()
        if claims.get('picture') and not user.avatar_url:
            user.avatar_url = claims['picture']
        user.save()
        return _tokens_para(user, status_code=201)

    return _tokens_para(user, status_code=200)


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
    attributes = _extract_attributes(request)
    if attributes is None:
        return _error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = UpdateProfileSerializer(data=attributes, partial=True)
    if not serializer.is_valid():
        errors = [
            {"status": "400", "source": {"pointer": f"/data/attributes/{field}"}, "detail": str(msgs[0])}
            for field, msgs in serializer.errors.items()
        ]
        return {"errors": errors}, 400

    user = cast(Users, request.user)
    for field, value in serializer.validated_data.items():
        setattr(user, field, value)
    user.save()

    return get_perfil_usuario(user), 200
