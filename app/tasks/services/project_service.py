from typing import Any, cast

from rest_framework.request import Request
from app.users.models import Users
from ..models import Project
from ..serializers.create_project_serializer import CreateProjectSerializer
from ..serializers.update_project_serializer import UpdateProjectSerializer
from app.organizations.access import Access, get_org_and_group
from app.common.jsonapi import error, parse_body


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
    organization, group = get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    if not Access(cast(Users, request.user), organization).is_owner:
        return error(403, "Solo el owner puede crear proyectos")

    body, err = parse_body(request, CreateProjectSerializer)
    if err:
        return err

    project = Project.objects.create(group=group, name=body['name'])
    return {"data": _project_resource(project)}, 201


def listar_proyectos(request: Request, organization_id: int, group_id: int) -> tuple[dict[str, Any], int]:
    """Proyectos del grupo; visible para owner/admin o cualquier miembro del grupo (RF-24)."""
    organization, group = get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    if not Access(cast(Users, request.user), organization, group).can_view_group:
        return error(403, "No tenés acceso a este grupo")

    projects = Project.objects.filter(group=group)
    return {"data": [_project_resource(p) for p in projects]}, 200


def obtener_proyecto(
    request: Request, organization_id: int, group_id: int, project_id: int,
) -> tuple[dict[str, Any], int]:
    """Detalle de un proyecto; mismo criterio de acceso que listar_proyectos."""
    organization, group = get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    project = Project.objects.filter(id=project_id, group=group).first()
    if not project:
        return error(404, "Proyecto no encontrado")

    if not Access(cast(Users, request.user), organization, group).can_view_group:
        return error(403, "No tenés acceso a este grupo")

    return {"data": _project_resource(project)}, 200


def actualizar_proyecto(
    request: Request, organization_id: int, group_id: int, project_id: int,
) -> tuple[dict[str, Any], int]:
    """Renombra el proyecto; solo owner."""
    organization, group = get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    project = Project.objects.filter(id=project_id, group=group).first()
    if not project:
        return error(404, "Proyecto no encontrado")

    if not Access(cast(Users, request.user), organization).is_owner:
        return error(403, "Solo el owner puede modificar el proyecto")

    body, err = parse_body(request, UpdateProjectSerializer, partial=True)
    if err:
        return err

    if 'name' in body:
        project.name = body['name']
        project.save()

    return {"data": _project_resource(project)}, 200


def eliminar_proyecto(
    request: Request, organization_id: int, group_id: int, project_id: int,
) -> tuple[dict[str, Any] | None, int]:
    """Borra el proyecto (y en cascada sus tareas); solo owner (RF-22)."""
    organization, group = get_org_and_group(organization_id, group_id)
    if not organization or not group:
        return error(404, "Grupo no encontrado")

    project = Project.objects.filter(id=project_id, group=group).first()
    if not project:
        return error(404, "Proyecto no encontrado")

    if not Access(cast(Users, request.user), organization).is_owner:
        return error(403, "Solo el owner puede eliminar el proyecto")

    project.delete()
    return None, 204
