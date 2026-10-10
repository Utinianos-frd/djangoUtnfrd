import uuid

from ..models import Organization, Membership
from ..serializers.create_organization_serializer import CreateOrganizationSerializer
from ..serializers.update_organization_serializer import UpdateOrganizationSerializer
from ..serializers.join_serializer import JoinSerializer
from .common import error, extract_attributes, serializer_errors, get_role


def _organization_resource(organization, role):
    return {
        "type": "organizations",
        "id": str(organization.id),
        "attributes": {
            "name": organization.name,
            "plan": organization.plan,
            "plan_status": organization.plan_status,
            "overload_threshold": organization.overload_threshold,
            "role": role,
        },
    }


def _organization_response(organization, user):
    return {"data": _organization_resource(organization, get_role(user, organization))}


def _invite_response(organization):
    return {
        "data": {
            "type": "invitations",
            "id": str(organization.invite_token),
            "attributes": {
                "token": str(organization.invite_token),
                "active": organization.invite_active,
            },
        }
    }


def crear_organizacion(request):
    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = CreateOrganizationSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    organization = Organization.objects.create(name=serializer.validated_data['name'])
    Membership.objects.create(organization=organization, user=request.user, role=Membership.Role.OWNER)

    return _organization_response(organization, request.user), 201


def listar_organizaciones(request):
    memberships = Membership.objects.filter(user=request.user).select_related('organization')
    data = [_organization_resource(m.organization, m.role) for m in memberships]
    return {"data": data}, 200


def obtener_organizacion(request, organization_id):
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if get_role(request.user, organization) is None:
        return error(403, "No pertenecés a esta organización")

    return _organization_response(organization, request.user), 200


def actualizar_organizacion(request, organization_id):
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if get_role(request.user, organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede modificar la organización")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = UpdateOrganizationSerializer(data=attributes, partial=True)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    changed = False
    if 'name' in serializer.validated_data:
        organization.name = serializer.validated_data['name']
        changed = True
    if 'overload_threshold' in serializer.validated_data:
        organization.overload_threshold = serializer.validated_data['overload_threshold']
        changed = True
    if changed:
        organization.save()

    return _organization_response(organization, request.user), 200


def eliminar_organizacion(request, organization_id):
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if get_role(request.user, organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede eliminar la organización")

    organization.delete()
    return None, 204


def ver_invitacion(request, organization_id):
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if get_role(request.user, organization) not in (Membership.Role.OWNER, Membership.Role.ADMIN):
        return error(403, "No tenés permiso para ver el link de invitación")

    return _invite_response(organization), 200


def regenerar_invitacion(request, organization_id):
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if get_role(request.user, organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede regenerar el link de invitación")

    organization.invite_token = uuid.uuid4()
    organization.invite_active = True
    organization.save()

    return _invite_response(organization), 200


def desactivar_invitacion(request, organization_id):
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if get_role(request.user, organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede desactivar el link de invitación")

    organization.invite_active = False
    organization.save()

    return _invite_response(organization), 200


def unirse_a_organizacion(request):
    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = JoinSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    token = serializer.validated_data['token']
    organization = Organization.objects.filter(invite_token=token, invite_active=True).first()
    if not organization:
        return error(404, "Link de invitación inválido o inactivo")

    membership, created = Membership.objects.get_or_create(
        organization=organization,
        user=request.user,
        defaults={'role': Membership.Role.MEMBER},
    )
    if not created:
        return error(409, "Ya pertenecés a esta organización")

    return _organization_response(organization, request.user), 201
