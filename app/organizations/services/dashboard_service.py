"""Agrega los datos del panel de inicio (home) para el usuario autenticado.

Es una vista de solo lectura, cruzada entre todas las organizaciones/grupos a los
que pertenece el usuario. Reutiliza la lógica de carga del workload_service.
"""
from app.organizations.models import Group, GroupMembership, Organization
from app.tasks.models import Task, TaskDependency
from .workload_service import carga_activa, clasificar


def _group_load(group, threshold):
    """Carga de un grupo: la severidad más alta entre sus miembros."""
    severities = {clasificar(carga_activa(m.user), threshold) for m in group.memberships.all()}
    if 'overloaded' in severities:
        return 'Alta'
    if 'busy' in severities:
        return 'Media'
    return 'Baja'


def obtener_dashboard(request):
    user = request.user

    groups = list(
        Group.objects
        .filter(memberships__user=user)
        .select_related('organization')
        .prefetch_related('memberships__user', 'projects')
        .distinct()
    )
    orgs = list(Organization.objects.filter(memberships__user=user).distinct())
    threshold = orgs[0].overload_threshold if orgs else 5
    plan = 'pro' if any(o.plan == Organization.Plan.PRO for o in orgs) else 'free'

    groups_payload = []
    member_users = {}
    for g in groups:
        lead = next((m for m in g.memberships.all() if m.role == GroupMembership.Role.GROUP_LEAD), None)
        for m in g.memberships.all():
            member_users[m.user_id] = m.user
        groups_payload.append({
            'name': g.name,
            'lead': lead.user.username if lead else '—',
            'projects': len(g.projects.all()),
            'members': len(g.memberships.all()),
            'load': _group_load(g, threshold),
        })

    team_load = [
        {'initials': (u.username[:2] or '?').upper(), 'status': clasificar(carga_activa(u), threshold)}
        for u in member_users.values()
    ]

    project_ids = [p.id for g in groups for p in g.projects.all()]
    blocked_count = TaskDependency.objects.filter(
        dependency_type=TaskDependency.Type.FINISH_TO_START,
        blocked_task__project_id__in=project_ids,
    ).exclude(blocking_task__status=Task.Status.DONE).values_list('blocked_task_id', flat=True).distinct().count()

    # Actividad reciente, derivada de datos reales (no hay log de auditoría):
    # últimas tareas creadas e ingresos a grupos, mezclados por fecha.
    activity = []
    for t in Task.objects.filter(project_id__in=project_ids).order_by('-created_at')[:6]:
        activity.append({'icon': 'pi-plus-circle', 'text': f'Nueva tarea: {t.title}', 'at': t.created_at.isoformat()})
    for jm in GroupMembership.objects.filter(group__in=groups).select_related('user', 'group').order_by('-created_at')[:6]:
        activity.append({'icon': 'pi-user-plus', 'text': f'{jm.user.username} se unió a {jm.group.name}', 'at': jm.created_at.isoformat()})
    activity.sort(key=lambda a: a['at'], reverse=True)
    activity = activity[:6]

    return {
        'data': {
            'type': 'dashboard',
            'id': 'me',
            'attributes': {
                'groups_total': len(groups),
                'members_total': len(member_users),
                'blocked_count': blocked_count,
                'plan': plan,
                'groups': groups_payload,
                'team_load': team_load,
                'activity': activity,
            },
        },
    }, 200
