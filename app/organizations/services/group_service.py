from ..models import Organization, Group, GroupMembership, Membership
from ..serializers.create_group_serializer import CreateGroupSerializer
from ..serializers.update_group_serializer import UpdateGroupSerializer
from .common import error, extract_attributes, serializer_errors, get_role


def _group_resource(group):
    return {
        "type": "groups",
        "id": str(group.id),
        "attributes": {
            "name": group.name,
            "organization_id": group.organization_id,
        },
    }


def _can_view_group(user, organization, group):
    role = get_role(user, organization)
    if role in (Membership.Role.OWNER, Membership.Role.ADMIN):
        return True
    return GroupMembership.objects.filter(group=group, user=user).exists()


def crear_grupo(request, organization_id):
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    if get_role(request.user, organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede crear grupos")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = CreateGroupSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    group = Group.objects.create(organization=organization, name=serializer.validated_data['name'])
    return {"data": _group_resource(group)}, 201


def listar_grupos(request, organization_id):
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    role = get_role(request.user, organization)
    if role is None:
        return error(403, "No pertenecés a esta organización")

    if role in (Membership.Role.OWNER, Membership.Role.ADMIN):
        groups = Group.objects.filter(organization=organization)
    else:
        groups = Group.objects.filter(organization=organization, memberships__user=request.user)

    return {"data": [_group_resource(g) for g in groups]}, 200


def obtener_grupo(request, organization_id, group_id):
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    group = Group.objects.filter(id=group_id, organization=organization).first()
    if not group:
        return error(404, "Grupo no encontrado")

    if not _can_view_group(request.user, organization, group):
        return error(403, "No tenés acceso a este grupo")

    return {"data": _group_resource(group)}, 200


def actualizar_grupo(request, organization_id, group_id):
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    group = Group.objects.filter(id=group_id, organization=organization).first()
    if not group:
        return error(404, "Grupo no encontrado")

    if get_role(request.user, organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede modificar el grupo")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = UpdateGroupSerializer(data=attributes, partial=True)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    if 'name' in serializer.validated_data:
        group.name = serializer.validated_data['name']
        group.save()

    return {"data": _group_resource(group)}, 200


def eliminar_grupo(request, organization_id, group_id):
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return error(404, "Organización no encontrada")

    group = Group.objects.filter(id=group_id, organization=organization).first()
    if not group:
        return error(404, "Grupo no encontrado")

    if get_role(request.user, organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede eliminar el grupo")

    group.delete()
    return None, 204
