from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from app.users.models import Users
from app.tasks.models import Project, Task, Comment, TaskDependency
from app.focus.models import FocusSession, Pomodoro
from ..models import Organization, Membership, Group, GroupMembership

_ORG_NAME = 'Tasker Demo'

# --- Usuarios -------------------------------------------------------------------------------------
# Los 5 primeros cubren un rol cada uno (ver specs/seed-de-datos-de-prueba.md). El resto son
# compañeros "de relleno" para que los grupos, el workload y el dashboard tengan algo que mostrar.
_USERS: list[dict[str, Any]] = [
    {'username': 'owner', 'first_name': 'Olivia', 'last_name': 'Ortega', 'org_role': Membership.Role.OWNER},
    {'username': 'admin', 'first_name': 'Andrés', 'last_name': 'Acosta', 'org_role': Membership.Role.ADMIN},
    {'username': 'member', 'first_name': 'Martina', 'last_name': 'Molina', 'org_role': Membership.Role.MEMBER},
    {'username': 'grouplead', 'first_name': 'Gonzalo', 'last_name': 'Gómez', 'org_role': Membership.Role.MEMBER},
    {'username': 'contributor', 'first_name': 'Camila', 'last_name': 'Castro', 'org_role': Membership.Role.MEMBER},
    {'username': 'lucia', 'first_name': 'Lucía', 'last_name': 'Fernández', 'org_role': Membership.Role.MEMBER},
    {'username': 'mateo', 'first_name': 'Mateo', 'last_name': 'Rossi', 'org_role': Membership.Role.MEMBER},
    {'username': 'sofia', 'first_name': 'Sofía', 'last_name': 'Pereyra', 'org_role': Membership.Role.MEMBER},
]

# --- Grupos: nombre -> [(username, rol de grupo)] -------------------------------------------------
_GROUPS: dict[str, list[tuple[str, str]]] = {
    'Backend': [
        ('grouplead', GroupMembership.Role.GROUP_LEAD),
        ('contributor', GroupMembership.Role.CONTRIBUTOR),
        ('sofia', GroupMembership.Role.CONTRIBUTOR),
    ],
    'Frontend': [
        ('lucia', GroupMembership.Role.GROUP_LEAD),
        ('mateo', GroupMembership.Role.CONTRIBUTOR),
        ('contributor', GroupMembership.Role.CONTRIBUTOR),
    ],
}

P, IP, D = Task.Status.PENDING, Task.Status.IN_PROGRESS, Task.Status.DONE

# --- Proyectos y tareas: grupo -> proyecto -> [(título, descripción, estado, asignados, días atrás)] --
# 'días atrás' = antigüedad de la tarea; las 'done' se cierran la mitad de días después de creadas.
# La carga quedó armada a propósito: 'contributor' sobrecargada (>= 5 activas), 'mateo' disponible.
_PROJECTS: dict[str, dict[str, list[tuple[str, str, str, list[str], int]]]] = {
    'Backend': {
        'API v2': [
            ('Diseñar esquema de autenticación', 'Definir flujo JWT con refresh tokens.', D, ['grouplead'], 30),
            ('Endpoint de login', 'POST /auth/login con validación de credenciales.', D, ['contributor'], 28),
            ('Endpoint de registro', 'Alta de usuarios con validación de email único.', IP, ['contributor'], 20),
            ('Paginación en listados', 'Agregar paginación JSON:API a todos los listados.', P, ['contributor', 'sofia'], 14),
            ('Rate limiting', 'Limitar requests por IP en endpoints públicos.', P, ['sofia'], 10),
            ('Documentar API en Swagger', 'Completar ejemplos de drf-spectacular.', P, ['contributor'], 5),
        ],
        'Migración a Postgres 16': [
            ('Backup de la base actual', 'Dump completo y verificación de restore.', D, ['grouplead'], 25),
            ('Probar migraciones en staging', 'Correr todas las migraciones sobre una copia.', IP, ['contributor'], 12),
            ('Actualizar docker-compose', 'Subir la imagen de postgres a la 16.', IP, ['sofia'], 8),
            ('Ventana de mantenimiento', 'Coordinar fecha y aviso a usuarios.', P, ['grouplead', 'contributor'], 3),
        ],
    },
    'Frontend': {
        'Rediseño Landing': [
            ('Wireframes de la home', 'Bocetos low-fi de las tres secciones principales.', D, ['lucia'], 22),
            ('Paleta y tipografía', 'Definir tokens de color y fuentes.', D, ['mateo'], 18),
            ('Maquetar hero', 'Hero responsive con CTA principal.', D, ['mateo'], 12),
            ('Sección de precios', 'Tabla de planes Free / Pro.', IP, ['lucia'], 6),
            ('Formulario de contacto', 'Validación en cliente y envío a la API.', P, ['lucia'], 2),
        ],
        'App Mobile': [
            ('Setup del proyecto', 'Inicializar repo y CI.', D, ['lucia'], 15),
            ('Pantalla de login', 'Consumir /auth/login y guardar tokens.', P, ['contributor'], 4),
        ],
    },
}

# --- Dependencias: (proyecto, tarea que bloquea, tarea bloqueada, tipo) -----------------------------
# Todas respetan los estados de arriba (FS: la bloqueada sigue 'pending' mientras la otra no esté 'done').
_DEPENDENCIES: list[tuple[str, str, str, str]] = [
    ('API v2', 'Diseñar esquema de autenticación', 'Endpoint de login', TaskDependency.Type.FINISH_TO_START),
    ('API v2', 'Endpoint de registro', 'Documentar API en Swagger', TaskDependency.Type.FINISH_TO_START),
    ('API v2', 'Endpoint de registro', 'Paginación en listados', TaskDependency.Type.FINISH_TO_FINISH),
    ('Migración a Postgres 16', 'Probar migraciones en staging', 'Ventana de mantenimiento', TaskDependency.Type.FINISH_TO_START),
    ('Migración a Postgres 16', 'Backup de la base actual', 'Probar migraciones en staging', TaskDependency.Type.FINISH_TO_START),
    ('Rediseño Landing', 'Paleta y tipografía', 'Maquetar hero', TaskDependency.Type.FINISH_TO_START),
    ('Rediseño Landing', 'Sección de precios', 'Formulario de contacto', TaskDependency.Type.FINISH_TO_START),
    ('App Mobile', 'Setup del proyecto', 'Pantalla de login', TaskDependency.Type.FINISH_TO_START),
]

# --- Comentarios: (proyecto, tarea, autor, texto) -------------------------------------------------
_COMMENTS: list[tuple[str, str, str, str]] = [
    ('API v2', 'Endpoint de registro', 'grouplead', '¿Validamos también el formato del teléfono acá?'),
    ('API v2', 'Endpoint de registro', 'contributor', 'Por ahora solo email y username, el teléfono queda para el perfil.'),
    ('API v2', 'Paginación en listados', 'sofia', 'Propongo page[number] y page[size] como dice JSON:API.'),
    ('API v2', 'Rate limiting', 'admin', 'Prioridad media, no bloquea el release.'),
    ('Migración a Postgres 16', 'Probar migraciones en staging', 'contributor', 'La 0004 tarda bastante, revisar índices.'),
    ('Migración a Postgres 16', 'Ventana de mantenimiento', 'owner', 'Mejor un domingo a la mañana.'),
    ('Rediseño Landing', 'Sección de precios', 'mateo', 'Te paso los íconos de cada plan en Figma.'),
    ('Rediseño Landing', 'Sección de precios', 'lucia', '¡Genial, gracias!'),
    ('App Mobile', 'Pantalla de login', 'lucia', 'Arranco cuando cierre el setup de CI.'),
]


def _password_for(username: str) -> str:
    """Password determinística por username, así siempre es predecible para el equipo."""
    return f'{username}123'


def _get_or_create_user(entry: dict[str, Any]) -> Users:
    """Crea el usuario si no existe y siempre resetea su password (idempotente, ver specs/seed-de-datos-de-prueba.md)."""
    username = entry['username']
    user, _ = Users.objects.get_or_create(
        username=username,
        defaults={
            'email': f'{username}@tasker.test',
            'role': 'user',
            'first_name': entry.get('first_name', ''),
            'last_name': entry.get('last_name', ''),
        },
    )
    user.set_password(_password_for(username))
    user.save()
    return user


def _seed_tasks(groups: dict[str, Group], users: dict[str, Users]) -> dict[tuple[str, str], Task]:
    """Crea proyectos y tareas; devuelve las tareas indexadas por (proyecto, título)."""
    now = timezone.now()
    tasks: dict[tuple[str, str], Task] = {}
    for group_name, projects in _PROJECTS.items():
        for project_name, task_rows in projects.items():
            project, _ = Project.objects.get_or_create(group=groups[group_name], name=project_name)
            for title, description, status, assignees, days_ago in task_rows:
                created_at = now - timedelta(days=days_ago)
                closed_at = created_at + timedelta(days=days_ago / 2) if status == D else None
                task, created = Task.objects.get_or_create(
                    project=project,
                    title=title,
                    defaults={'description': description, 'status': status, 'closed_at': closed_at},
                )
                if created:
                    # auto_now_add pisa created_at en el create, así que se backdatea después.
                    Task.objects.filter(pk=task.pk).update(created_at=created_at)
                    task.assignees.set([users[u] for u in assignees])
                tasks[(project_name, title)] = task
    return tasks


def _seed_focus(users: dict[str, Users], tasks: dict[tuple[str, str], Task]) -> int:
    """Una sesión terminada (con historial) para 'contributor' y una activa para 'grouplead'."""
    now = timezone.now()
    sessions: list[dict[str, Any]] = [
        {
            'user': 'contributor',
            'goal': 'Cerrar el endpoint de registro',
            'status': FocusSession.Status.ENDED,
            'started': now - timedelta(days=1, hours=3),
            'tasks': [('API v2', 'Endpoint de registro'), ('API v2', 'Documentar API en Swagger')],
            'pomodoros': [Pomodoro.Status.COMPLETED, Pomodoro.Status.COMPLETED, Pomodoro.Status.CANCELLED],
        },
        {
            'user': 'grouplead',
            'goal': 'Planificar la ventana de mantenimiento',
            'status': FocusSession.Status.ACTIVE,
            'started': now - timedelta(minutes=40),
            'tasks': [('Migración a Postgres 16', 'Ventana de mantenimiento')],
            'pomodoros': [Pomodoro.Status.COMPLETED, Pomodoro.Status.RUNNING],
        },
    ]
    count = 0
    for s in sessions:
        user = users[s['user']]
        if s['status'] == FocusSession.Status.ACTIVE and FocusSession.objects.filter(
            user=user, status=FocusSession.Status.ACTIVE,
        ).exclude(goal_text=s['goal']).exists():
            continue  # el usuario ya tiene otra sesión activa (creada probando); no la pisamos
        session, created = FocusSession.objects.get_or_create(
            user=user,
            goal_text=s['goal'],
            defaults={'status': s['status']},
        )
        count += 1
        if not created:
            continue
        session_tasks = [tasks[k] for k in s['tasks']]
        session.tasks.set(session_tasks)
        ended_at = s['started'] + timedelta(minutes=30 * len(s['pomodoros']))
        FocusSession.objects.filter(pk=session.pk).update(
            started_at=s['started'],
            ended_at=ended_at if s['status'] == FocusSession.Status.ENDED else None,
        )
        for i, pomo_status in enumerate(s['pomodoros']):
            started = s['started'] + timedelta(minutes=30 * i)
            pomodoro = Pomodoro.objects.create(session=session, task=session_tasks[i % len(session_tasks)], status=pomo_status)
            Pomodoro.objects.filter(pk=pomodoro.pk).update(
                started_at=started,
                completed_at=started + timedelta(minutes=Pomodoro.DURATION_MINUTES) if pomo_status == Pomodoro.Status.COMPLETED else None,
            )
    return count


@transaction.atomic
def run_seed() -> dict[str, Any]:
    """Crea (o reutiliza) la org demo con usuarios de cada rol, grupos, proyectos, tareas, dependencias,
    comentarios y sesiones de foco; solo con DEBUG=True."""
    organization, _ = Organization.objects.get_or_create(name=_ORG_NAME)
    # Plan Pro para que el Modo Foco esté habilitado con los datos de prueba.
    organization.plan = Organization.Plan.PRO
    organization.plan_status = Organization.PlanStatus.ACTIVE
    organization.save(update_fields=['plan', 'plan_status'])

    users: dict[str, Users] = {}
    for entry in _USERS:
        user = _get_or_create_user(entry)
        users[entry['username']] = user
        Membership.objects.get_or_create(
            organization=organization,
            user=user,
            defaults={'role': entry['org_role']},
        )

    groups: dict[str, Group] = {}
    group_roles: dict[str, dict[str, str]] = {}  # username -> {grupo: rol}
    for group_name, members in _GROUPS.items():
        group, _ = Group.objects.get_or_create(organization=organization, name=group_name)
        groups[group_name] = group
        for username, role in members:
            GroupMembership.objects.get_or_create(group=group, user=users[username], defaults={'role': role})
            group_roles.setdefault(username, {})[group_name] = role

    tasks = _seed_tasks(groups, users)

    for project_name, blocking, blocked, dep_type in _DEPENDENCIES:
        TaskDependency.objects.get_or_create(
            blocking_task=tasks[(project_name, blocking)],
            blocked_task=tasks[(project_name, blocked)],
            defaults={'dependency_type': dep_type},
        )

    for project_name, title, author, text in _COMMENTS:
        Comment.objects.get_or_create(task=tasks[(project_name, title)], author=users[author], text=text)

    focus_sessions = _seed_focus(users, tasks)

    credentials: list[dict[str, Any]] = [
        {
            'username': entry['username'],
            'password': _password_for(entry['username']),
            'org_role': entry['org_role'],
            'group_roles': group_roles.get(entry['username'], {}),
        }
        for entry in _USERS
    ]

    return {
        'organization': organization.name,
        'groups': list(groups),
        'summary': {
            'users': len(users),
            'projects': sum(len(p) for p in _PROJECTS.values()),
            'tasks': len(tasks),
            'dependencies': len(_DEPENDENCIES),
            'comments': len(_COMMENTS),
            'focus_sessions': focus_sessions,
        },
        'credentials': credentials,
    }
