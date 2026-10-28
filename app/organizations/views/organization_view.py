from typing import Any
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..services.organization_service import (
    crear_organizacion,
    listar_organizaciones,
    obtener_organizacion,
    actualizar_organizacion,
    eliminar_organizacion,
    ver_invitacion,
    regenerar_invitacion,
    desactivar_invitacion,
    unirse_a_organizacion,
)


@extend_schema(
    tags=['Organizations'],
    summary='Crear organización (POST) / listar mis organizaciones (GET)',
    description=(
        'POST: crea una organización y asigna automáticamente al usuario autenticado como owner. '
        'GET: lista las organizaciones a las que pertenece el usuario autenticado, con su rol en cada una.'
    ),
)
@api_view(['GET', 'POST'])
def organizations(request: Request) -> Response:
    if request.method == 'POST':
        data, status = crear_organizacion(request)
    else:
        data, status = listar_organizaciones(request)
    return Response(data, status=status)


@extend_schema(
    tags=['Organizations'],
    summary='Ver (GET) / editar (PATCH) / eliminar (DELETE) una organización',
    description='PATCH y DELETE requieren ser owner de la organización. GET requiere ser miembro.',
)
@api_view(['GET', 'PATCH', 'DELETE'])
def organization_detail(request: Request, organization_id: int) -> Response:
    data: dict[str, Any] | None
    if request.method == 'GET':
        data, status = obtener_organizacion(request, organization_id)
    elif request.method == 'PATCH':
        data, status = actualizar_organizacion(request, organization_id)
    else:
        data, status = eliminar_organizacion(request, organization_id)
    return Response(data, status=status)


@extend_schema(
    tags=['Organizations'],
    summary='Ver el link de invitación de la organización',
    description='Requiere ser owner o admin de la organización.',
)
@api_view(['GET'])
def invite_detail(request: Request, organization_id: int) -> Response:
    data, status = ver_invitacion(request, organization_id)
    return Response(data, status=status)


@extend_schema(
    tags=['Organizations'],
    summary='Regenerar el link de invitación',
    description='Invalida el link anterior y genera un token nuevo. Requiere ser owner.',
)
@api_view(['POST'])
def invite_regenerate(request: Request, organization_id: int) -> Response:
    data, status = regenerar_invitacion(request, organization_id)
    return Response(data, status=status)


@extend_schema(
    tags=['Organizations'],
    summary='Desactivar el link de invitación',
    description='Requiere ser owner.',
)
@api_view(['POST'])
def invite_deactivate(request: Request, organization_id: int) -> Response:
    data, status = desactivar_invitacion(request, organization_id)
    return Response(data, status=status)


@extend_schema(
    tags=['Organizations'],
    summary='Unirse a una organización vía link de invitación',
    description='El usuario autenticado queda como member de la organización dueña del token.',
)
@api_view(['POST'])
def join(request: Request) -> Response:
    data, status = unirse_a_organizacion(request)
    return Response(data, status=status)
