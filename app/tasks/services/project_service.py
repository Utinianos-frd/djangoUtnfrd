from typing import Any, cast

from rest_framework.request import Request
from app.users.models import Users
from app.organizations.models import Organization, Group, Membership, GroupMembership
from ..models import Project
from ..serializers.create_project_serializer import CreateProjectSerializer
from ..serializers.update_project_serializer import UpdateProjectSerializer
from .common import error, extract_attributes, serializer_errors


def _org_role(user: Users, organization: Organization) -> str | None:
    """Rol del usuario en esta organización, o None si no es miembro."""
    membership = Membership.objects.filter(organization=organization, user=user).first()
    return membership.role if membership else None


def _group_role(user: Users, group: Group) -> str | None:
    """Rol del usuario en este grupo, o None si no pertenece."""
    membership = GroupMembership.objects.filter(group=group, user=user).first()
    return membership.role if membership else None


def _can_view(user: Users, organization: Organization, group: Group) -> bool:
    """Owner/admin (oversight) o cualquier miembro del grupo (group lead o contributor)."""
    role = _org_role(user, organization)
    if role in (Membership.Role.OWNER, Membership.Role.ADMIN):
        return True
    return _group_role(user, group) is not None


def _get_org_and_group(organization_id: int, group_id: int) -> tuple[Organization | None, Group | None]:
    """Resuelve (organization, group) por id, o (None, None)/(org, None) si no existen."""
    organization = Organization.objects.filter(id=organization_id).first()
    if not organization:
        return None, None
    group = Group.objects.filter(id=group_id, organization=organization).first()
    return organization, group


def _project_resource(project: Project) -> dict[str, Any]:
    """Recurso JSON:API de un Project."""
    return {
        "type": "projects",
        "id": str(project.id),
        "attributes": {
            "name": project.name,
            "group_id": project.group_id,
        },
    }


def crear_proyecto(request: Request, organization_id: int, group_id: int) -> tuple[dict[str, Any], int]:
    """Crea el proyecto con el grupo ya fijado por la URL (RF-20/RF-21 unificados); solo owner."""
    organization, group = _get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    if _org_role(cast(Users, request.user), organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede crear proyectos")

    attributes = extract_attributes(request)
    if attributes is None:
        return error(400, "El body debe seguir la estructura JSON:API: { data: { type, attributes } }")

    serializer = CreateProjectSerializer(data=attributes)
    if not serializer.is_valid():
        return {"errors": serializer_errors(serializer)}, 400

    project = Project.objects.create(group=group, name=serializer.validated_data['name'])
    return {"data": _project_resource(project)}, 201


def listar_proyectos(request: Request, organization_id: int, group_id: int) -> tuple[dict[str, Any], int]:
    """Proyectos del grupo; visible para owner/admin o cualquier miembro del grupo (RF-24)."""
    organization, group = _get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    if not _can_view(cast(Users, request.user), organization, group):
        return error(403, "No tenés acceso a este grupo")

    projects = Project.objects.filter(group=group)
    return {"data": [_project_resource(p) for p in projects]}, 200


def obtener_proyecto(
    request: Request, organization_id: int, group_id: int, project_id: int,
) -> tuple[dict[str, Any], int]:
    """Detalle de un proyecto; mismo criterio de acceso que listar_proyectos."""
    organization, group = _get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    project = Project.objects.filter(id=project_id, group=group).first()
    if not project:
        return error(404, "Proyecto no encontrado")

    if not _can_view(cast(Users, request.user), organization, group):
        return error(403, "No tenés acceso a este grupo")

    return {"data": _project_resource(project)}, 200


def actualizar_proyecto(
    request: Request, organization_id: int, group_id: int, project_id: int,
) -> tuple[dict[str, Any], int]:
    """Renombra el proyecto; solo owner."""
    organization, group = _get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    project = Project.objects.filter(id=project_id, group=group).first()
    if not project:
        return error(404, "Proyecto no encontrado")

    if _org_role(cast(Users, request.user), organization) != Membership.Role.OWNER:
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


def eliminar_proyecto(
    request: Request, organization_id: int, group_id: int, project_id: int,
) -> tuple[dict[str, Any] | None, int]:
    """Borra el proyecto (y en cascada sus tareas); solo owner (RF-22)."""
    organization, group = _get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    project = Project.objects.filter(id=project_id, group=group).first()
    if not project:
        return error(404, "Proyecto no encontrado")

    if _org_role(cast(Users, request.user), organization) != Membership.Role.OWNER:
        return error(403, "Solo el owner puede eliminar el proyecto")

    project.delete()
    return None, 204
