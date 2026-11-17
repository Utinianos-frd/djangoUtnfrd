from typing import cast
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from ..models.users import Users
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from ..services.auth_service import login_usuario, register_usuario, google_login_usuario, get_perfil_usuario, update_perfil_usuario


_JSONAPI_ERROR_EXAMPLE = OpenApiExample(
    'Error',
    value={"errors": [{"status": "400", "detail": "Descripción del error"}]},
    response_only=True,
    status_codes=['400', '401', '409'],
)


@extend_schema(
    tags=['Auth'],
    summary='Iniciar sesión',
    description='Autentica un usuario y devuelve tokens JWT de acceso y refresco.',
    request={
        'application/json': {
            'type': 'object',
            'required': ['data'],
            'properties': {
                'data': {
                    'type': 'object',
                    'required': ['type', 'attributes'],
                    'properties': {
                        'type': {'type': 'string', 'enum': ['sessions']},
                        'attributes': {
                            'type': 'object',
                            'required': ['username', 'password'],
                            'properties': {
                                'username': {'type': 'string', 'example': 'alex'},
                                'password': {'type': 'string', 'example': 'secret123'},
                            },
                        },
                    },
                }
            },
        }
    },
    responses={
        200: OpenApiResponse(
            description='Login exitoso',
            examples=[OpenApiExample(
                'Éxito',
                value={
                    "data": {
                        "type": "sessions",
                        "attributes": {
                            "access": "<jwt_access_token>",
                            "refresh": "<jwt_refresh_token>",
                            "exp": "2026-05-23T18:45:00Z",
                        },
                    }
                },
                response_only=True,
                status_codes=['200'],
            )],
        ),
        400: OpenApiResponse(description='Body inválido', examples=[_JSONAPI_ERROR_EXAMPLE]),
        401: OpenApiResponse(description='Credenciales incorrectas', examples=[_JSONAPI_ERROR_EXAMPLE]),
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request: Request) -> Response:
    """POST /auth/login — wrapper fino sobre auth_service.login_usuario."""
    data, status = login_usuario(request)
    return Response(data, status=status)


@extend_schema(
    tags=['Auth'],
    summary='Registrar usuario',
    description='Crea un nuevo usuario y devuelve tokens JWT.',
    request={
        'application/json': {
            'type': 'object',
            'required': ['data'],
            'properties': {
                'data': {
                    'type': 'object',
                    'required': ['type', 'attributes'],
                    'properties': {
                        'type': {'type': 'string', 'enum': ['users']},
                        'attributes': {
                            'type': 'object',
                            'required': ['username', 'email', 'password'],
                            'properties': {
                                'username': {'type': 'string', 'example': 'alex'},
                                'email': {'type': 'string', 'format': 'email', 'example': 'alex@example.com'},
                                'password': {'type': 'string', 'minLength': 8, 'example': 'secret123'},
                            },
                        },
                    },
                }
            },
        }
    },
    responses={
        201: OpenApiResponse(
            description='Usuario creado',
            examples=[OpenApiExample(
                'Éxito',
                value={
                    "data": {
                        "type": "sessions",
                        "attributes": {
                            "access": "<jwt_access_token>",
                            "refresh": "<jwt_refresh_token>",
                        },
                    }
                },
                response_only=True,
                status_codes=['201'],
            )],
        ),
        400: OpenApiResponse(description='Datos inválidos', examples=[
            OpenApiExample(
                'Error de validación',
                value={
                    "errors": [
                        {"status": "400", "source": {"pointer": "/data/attributes/email"}, "detail": "Enter a valid email address."}
                    ]
                },
                response_only=True,
                status_codes=['400'],
            )
        ]),
        409: OpenApiResponse(description='Usuario ya existe', examples=[_JSONAPI_ERROR_EXAMPLE]),
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request: Request) -> Response:
    """POST /auth/register — wrapper fino sobre auth_service.register_usuario."""
    data, status = register_usuario(request)
    return Response(data, status=status)


@extend_schema(
    tags=['Auth'],
    summary='Iniciar sesión / registrarse con Google',
    description=(
        'Recibe el `id_token` que emite Google Identity Services en el frontend, lo valida '
        'contra Google y busca o crea el usuario con ese email. Devuelve tokens JWT igual que '
        'el login normal (201 si la cuenta se creó en esta llamada, 200 si ya existía).'
    ),
    request={
        'application/json': {
            'type': 'object',
            'required': ['data'],
            'properties': {
                'data': {
                    'type': 'object',
                    'required': ['type', 'attributes'],
                    'properties': {
                        'type': {'type': 'string', 'enum': ['sessions']},
                        'attributes': {
                            'type': 'object',
                            'required': ['id_token'],
                            'properties': {
                                'id_token': {'type': 'string', 'example': '<google_id_token>'},
                            },
                        },
                    },
                }
            },
        }
    },
    responses={
        200: OpenApiResponse(description='Sesión iniciada (cuenta existente)'),
        201: OpenApiResponse(description='Cuenta creada e iniciada'),
        400: OpenApiResponse(description='Falta el id_token o body inválido', examples=[_JSONAPI_ERROR_EXAMPLE]),
        401: OpenApiResponse(description='Token de Google inválido', examples=[_JSONAPI_ERROR_EXAMPLE]),
        503: OpenApiResponse(description='Login con Google no configurado', examples=[_JSONAPI_ERROR_EXAMPLE]),
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def google_login(request: Request) -> Response:
    """POST /auth/google — wrapper fino sobre auth_service.google_login_usuario."""
    data, status = google_login_usuario(request)
    return Response(data, status=status)


@extend_schema(
    tags=['Auth'],
    summary='Perfil del usuario autenticado',
    description='Devuelve los datos del usuario que realiza la petición. Requiere JWT en el header `Authorization: Bearer <token>`.',
    responses={
        200: OpenApiResponse(
            description='Perfil del usuario',
            examples=[OpenApiExample(
                'Éxito',
                value={
                    "data": {
                        "type": "users",
                        "id": "1",
                        "attributes": {
                            "username": "alex",
                            "email": "alex@example.com",
                            "role": "user",
                        },
                        "links": {"self": "/api/users/1"},
                    }
                },
                response_only=True,
                status_codes=['200'],
            )],
        ),
        401: OpenApiResponse(description='No autenticado'),
    },
)
@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def me(request: Request) -> Response:
    """GET /auth/me — perfil del usuario. PATCH /auth/me — edita el perfil."""
    if request.method == 'PATCH':
        data, status = update_perfil_usuario(request)
        return Response(data, status=status)
    data = get_perfil_usuario(cast(Users, request.user))
    return Response(data, status=200)
