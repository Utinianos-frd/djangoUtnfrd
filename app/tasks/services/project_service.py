from app.organizations.models import Organization, Group, Membership, GroupMembership
from ..models import Project
from ..serializers.create_project_serializer import CreateProjectSerializer
from ..serializers.update_project_serializer import UpdateProjectSerializer
from .common import error, extract_attributes, serializer_errors


def _org_role(user, organization):
    membership = Membership.objects.filter(organization=organization, user=user).first()
    return membership.role if membership else None


def _group_role(user, group):
    membership = GroupMembership.objects.filter(group=group, user=user).first()
    return membership.role if membership else None


def _can_view(user, organization, group):
    role = _org_role(user, organization)
    if role in (Membership.Role.OWNER, Membership.Role.ADMIN):
        return True
    return _group_role(user, group) is not None


def _get_org_and_group(organization_id, group_id):
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return None, None
    group = Group.objects.filter(id=group_id, organization=organization).first()
    return organization, group


def _project_resource(project):
    return {
        "type": "projects",
        "id": str(project.id),
        "attributes": {
            "name": project.name,
            "group_id": project.group_id,
        },
    }


def crear_proyecto(request, organization_id, group_id):
    organization, group = _get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    if _org_role(request.user, organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede crear proyectos")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = CreateProjectSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    project = Project.objects.create(group=group, name=serializer.validated_data['name'])
    return {"data": _project_resource(project)}, 201


def listar_proyectos(request, organization_id, group_id):
    organization, group = _get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    if not _can_view(request.user, organization, group):
        return error(403, "No tenés acceso a este grupo")

    projects = Project.objects.filter(group=group)
    return {"data": [_project_resource(p) for p in projects]}, 200


def obtener_proyecto(request, organization_id, group_id, project_id):
    organization, group = _get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    project = Project.objects.filter(id=project_id, group=group).first()
    if not project:
        return error(404, "Proyecto no encontrado")

    if not _can_view(request.user, organization, group):
        return error(403, "No tenés acceso a este grupo")

    return {"data": _project_resource(project)}, 200


def actualizar_proyecto(request, organization_id, group_id, project_id):
    organization, group = _get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    project = Project.objects.filter(id=project_id, group=group).first()
    if not project:
        return error(404, "Proyecto no encontrado")

    if _org_role(request.user, organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede modificar el proyecto")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = UpdateProjectSerializer(data=attributes, partial=True)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    if 'name' in serializer.validated_data:
        project.name = serializer.validated_data['name']
        project.save()

    return {"data": _project_resource(project)}, 200


def eliminar_proyecto(request, organization_id, group_id, project_id):
    organization, group = _get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    project = Project.objects.filter(id=project_id, group=group).first()
    if not project:
        return error(404, "Proyecto no encontrado")

    if _org_role(request.user, organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede eliminar el proyecto")

    project.delete()
    return None, 204
