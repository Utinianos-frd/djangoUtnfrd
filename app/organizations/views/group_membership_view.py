from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..services.group_membership_service import (
    listar_miembros_grupo,
    agregar_miembro_grupo,
    cambiar_rol_miembro_grupo,
    eliminar_miembro_grupo,
)


@extend_schema(
    tags=['Groups'],
    summary='Listar (GET) / agregar (POST) miembros del grupo',
    description='GET: owner/admin o miembro del grupo. POST: solo el group lead, agrega un Member de la organización como contributor.',
)
@api_view(['GET', 'POST'])
def group_members(request, organization_id, group_id):
    if request.method == 'POST':
        data, status = agregar_miembro_grupo(request, organization_id, group_id)
    else:
        data, status = listar_miembros_grupo(request, organization_id, group_id)
    return Response(data, status=status)


@extend_schema(
    tags=['Groups'],
    summary='Cambiar rol de un miembro del grupo (PATCH) / eliminarlo (DELETE)',
    description=(
        'PATCH: solo el owner de la organización, para asignar role="group_lead" (el group lead saliente '
        'pasa a contributor automáticamente). DELETE: solo el group lead; no se puede eliminar al group lead.'
    ),
)
@api_view(['PATCH', 'DELETE'])
def group_member_detail(request, organization_id, group_id, user_id):
    if request.method == 'PATCH':
        data, status = cambiar_rol_miembro_grupo(request, organization_id, group_id, user_id)
    else:
        data, status = eliminar_miembro_grupo(request, organization_id, group_id, user_id)
    return Response(data, status=status)
