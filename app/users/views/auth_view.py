from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from ..services.auth_service import login_usuario, register_usuario, get_perfil_usuario


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
def login(request):
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
def register(request):
    data, status = register_usuario(request)
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
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    data = get_perfil_usuario(request.user)
    return Response(data, status=200)
