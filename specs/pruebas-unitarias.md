# Pruebas unitarias

Spec de la infraestructura de testing del proyecto y las convenciones para escribir tests nuevos. No es un requerimiento del documento de especificación de Tasker — es tooling de calidad interna, pero se documenta igual siguiendo la práctica ya establecida de este repo (un spec por cada pieza nueva).

> Cinco tandas, 233 tests en total, corridos contra una base Postgres real de test: `app/organizations` (59 tests: Organization, Membership, Group, GroupMembership), `app/tasks` (82 tests: Project, Task, Comment, TaskDependency, incluyendo detección de ciclos y bloqueo por dependencias), `app/focus` (44 tests: sesiones, máquina de estados del pomodoro, gate de plan Pro), `app/users` (22 tests: login, registro, `me` y el flujo JWT con refresh) y el Workload de `app/organizations` (26 tests). Solo queda sin tests el seed — ver sección 5.

## 1. Stack elegido

- **pytest + pytest-django** (no `unittest`/`manage.py test`). Se prefirió por la sintaxis de fixtures y `assert` simple sobre el estilo `TestCase`/`self.assertEqual` de Django — decisión explícita del usuario, discutida antes de empezar a escribir código.
- Dependencias nuevas en [requirements.txt](../requirements.txt): `pytest==9.1.1`, `pytest-django==4.14.0`.
- Configuración en [pytest.ini](../pytest.ini) (raíz del repo): apunta `DJANGO_SETTINGS_MODULE` a `config.settings`, restringe la búsqueda de tests a `app/` y usa `--import-mode=importlib`. Esto último hace falta porque los apps (`app/organizations`, `app/tasks`, …) no tienen `__init__.py`: con el modo por defecto, pytest veía todas las carpetas `tests/` como un mismo paquete `tests` y chocaban los `conftest.py`. Con `importlib` cada archivo se importa por su ruta (`app.tasks.tests.conftest`), así que las carpetas `tests/` **no llevan `__init__.py`**.
- El [conftest.py](../conftest.py) raíz cambia el hasher de passwords a MD5 solo durante los tests (fixture `autouse`): el PBKDF2 por defecto es lento a propósito y, como cada test crea varios usuarios, la suite pasaba de ~4 minutos a ~8 segundos.

## 2. Cómo correrlos

```bash
python -m pytest                          # toda la suite
python -m pytest app/organizations -v     # solo una app, verbose
bash commands/dev.sh test                 # atajo (ver commands/dev.sh)
bash commands/dev.sh test app/organizations -v
```

`pytest-django` crea una base de datos de test aparte (`test_<nombre de la DB real>`) contra el mismo servidor Postgres de `docker-compose`, corre todo ahí, y la destruye al terminar — **nunca toca los datos de la base de desarrollo real**. Cada test individual corre dentro de una transacción que se revierte sola al final (gracias a `pytest.mark.django_db`), así que no hace falta limpiar nada a mano como sí había que hacer en los smoke tests manuales de las tandas anteriores.

## 3. Estructura y convenciones

- **Una carpeta `tests/` por app (sin `__init__.py`, ver §1)** (`app/organizations/tests/`, y así para cada app a medida que se le sumen tests), no una carpeta `tests/` centralizada — mismo criterio modular que ya se usa con `services/`, `views/`, `serializers/` por app.
- **Fixtures compartidas entre todas las apps** en [conftest.py](../conftest.py) (raíz del repo, pytest lo descubre automáticamente):
  - `rf`: una `APIRequestFactory` limpia.
  - `call(view, method, path, user, data, **url_kwargs)`: invoca directamente la función de vista (los wrappers finos de `app/*/views/`) como si fuera un request HTTP real — sin pasar por el `urlconf` — y devuelve `(status_code, data)`. Es exactamente el mismo patrón que se usaba a mano en los smoke tests de las tandas anteriores, ahora formalizado como fixture.
  - `make_user(username=None, password='pass1234', **extra)`: factory de `Users.objects.create_user` con username único por llamada si no se especifica uno.
- **Fixtures propias de cada app** en `app/<app>/tests/conftest.py` — por ejemplo, `app/organizations/tests/conftest.py` define `make_organization` y `owner_org` (una organización con su owner ya creado), que son el punto de partida de casi todos los tests de esa app.
- **Un archivo de test por servicio**, agrupado en clases por acción (`class TestCrearOrganizacion:`, `class TestActualizarOrganizacion:`, etc.) — más legible que un archivo plano de funciones sueltas cuando hay 10+ casos por endpoint.
- **Se testea a nivel de vista, no de servicio puro ni de HTTP real**: como las vistas de este proyecto son wrappers de una sola línea sobre los servicios (`data, status = crear_organizacion(request); return Response(data, status=status)`), llamarlas directo da exactamente el mismo comportamiento que ejercitar el servicio, pero de paso valida también el parseo de `request.data` y la autenticación forzada (`force_authenticate`) — sin la sobrecarga de resolver URLs reales a través de Django. Mismo criterio que ya habíamos validado manualmente en todos los smoke tests previos.
- Cada clase de test cubre, como mínimo: el camino feliz, al menos un caso de permiso denegado por rol, y los casos de error de negocio no triviales (constraints, validaciones cruzadas) — no solo "funciona", sino "rechaza lo que tiene que rechazar".

## 4. Qué cubre esta primera tanda (`app/organizations`, 59 tests)

| Archivo | Qué cubre |
|---|---|
| [test_organization_service.py](../app/organizations/tests/test_organization_service.py) | Crear (incl. defaults de plan/logo/umbral), listar, ver, editar (`name`, `logo_url`, `overload_threshold`, validación de URL inválida), eliminar, invitación (ver/regenerar/desactivar), join (éxito, token inválido, token desactivado, ya-es-miembro), y los dos constraints de `Membership` a nivel de DB (`unique_owner_per_organization`, `unique_membership_per_user_per_organization`) |
| [test_membership_service.py](../app/organizations/tests/test_membership_service.py) | Listar miembros, cambiar rol (incluye el traspaso de ownership y el bloqueo de bajar al owner directamente), eliminar miembro (incluye que no se puede eliminar al owner) |
| [test_group_service.py](../app/organizations/tests/test_group_service.py) | Crear (solo owner), listar (owner/admin ven todos, member solo los suyos), ver/editar/eliminar |
| [test_group_membership_service.py](../app/organizations/tests/test_group_membership_service.py) | **El bug de bootstrap documentado en [grupos-abm.md §3](grupos_y_roles/grupos-abm.md)**, formalizado como test explícito (`TestBootstrapDelGroupLead`) para que no se reintroduzca sin que algo lo note; agregar miembro (validación cruzada con `Membership`, duplicados, permisos), traspaso de group lead, eliminar miembro (no se puede eliminar al group lead, el Owner no puede eliminar miembros de grupo directamente) |

## 4.1. Segunda tanda (`app/tasks`, 82 tests)

Fixtures propias en [app/tasks/tests/conftest.py](../app/tasks/tests/conftest.py): `org_group` arma el escenario completo (organización con un usuario por rol — `owner`, `admin`, `member` sin grupo, `lead`, `contributor`, `contributor2`, `outsider` sin membresía —, un grupo y un proyecto) y se accede como `org_group.lead`, `org_group.project`, etc.; `project_kwargs` da los `url_kwargs` de las vistas anidadas bajo el proyecto, y `make_task` crea tareas con asignados opcionales. Los chequeos de permisos por rol se escriben con `pytest.mark.parametrize('role', [...])` para cubrir todos los roles con un solo test.

| Archivo | Qué cubre |
|---|---|
| [test_project_service.py](../app/tasks/tests/test_project_service.py) | Crear (solo owner, 404 con org/grupo cruzados, body inválido), listar (owner/admin/miembros del grupo sí; member sin grupo y outsider no), ver, renombrar (solo owner), eliminar con cascada de tareas |
| [test_task_service.py](../app/tasks/tests/test_task_service.py) | Crear (solo group lead, asignados fuera del grupo, `meta.warnings` de sobrecarga con alternativas sugeridas), listar (contributor ve solo las suyas), ver, editar (group lead todo; contributor solo `status` de sus tareas), **bloqueo por dependencias** (FS impide arrancar y prende `blocked`, también frena al group lead, se libera al completar la bloqueante; FF deja arrancar pero no completar), eliminar |
| [test_comment_service.py](../app/tasks/tests/test_comment_service.py) | Comentar (group lead o contributor asignado; owner/admin pueden leer pero no comentar), orden cronológico, 404/400 |
| [test_dependency_service.py](../app/tasks/tests/test_dependency_service.py) | Crear (solo group lead, autodependencia, duplicada, tipo inválido, tarea de otro proyecto), **detección de ciclos** (directo, transitivo de 4 tareas, y un diamante que *no* es ciclo), listar (contributor ve solo las que tocan sus tareas), eliminar, cascadas y los dos constraints de DB (`unique_dependency_per_task_pair`, `no_self_dependency`) |

Se verificó que la suite detecta regresiones reales: rompiendo a mano `_creates_cycle` y la regla FS de `_dependency_block_reason`, fallan los tests correspondientes.

## 4.2. Tercera tanda (`app/focus`, 44 tests)

Fixtures propias en [app/focus/tests/conftest.py](../app/focus/tests/conftest.py): `focus_user` (un usuario con dos tareas asignadas en una organización Pro, más otro usuario sin nada), `active_session` (sesión activa sobre esas dos tareas) y `make_project(plan=...)` para armar organizaciones Free. Modo Foco no mira roles de organización ni de grupo — solo asignación de tareas y plan —, así que no se crean `Membership`.

Los tiempos (`started_at` es `auto_now_add`, `paused_at`) se controlan pisándolos con `Pomodoro.objects.filter(...).update(...)` en vez de mockear el reloj.

| Archivo | Qué cubre |
|---|---|
| [test_focus_session_service.py](../app/focus/tests/test_focus_session_service.py) | Iniciar sesión (**gate de plan Pro**, tarea no asignada, inexistente, lista vacía, ids repetidos), una sola sesión activa por usuario (servicio y constraint de DB), sesión activa, finalizar (resumen: tiempo trabajado descontando pausas, pomodoros completados, tareas en `done`; cancela pomodoros en curso; no se termina dos veces; sesión ajena da 404) |
| [test_pomodoro_service.py](../app/focus/tests/test_pomodoro_service.py) | Iniciar pomodoro (uno en curso por sesión, tarea fuera de la sesión, sesión terminada o ajena), **máquina de estados** completa (transiciones válidas y las 11 inválidas con `parametrize`, acumulado de tiempo pausado al reanudar), **descanso sugerido** (5 min, 15 min al cuarto seguido, un cancelado corta la racha) |

Igual que en la tanda anterior, se verificó rompiendo a mano el gate de plan Pro, el acumulado de pausas y el corte de racha: fallan los tests correspondientes.

## 4.3. Cuarta tanda (`app/users`, 22 tests)

| Archivo | Qué cubre |
|---|---|
| [test_auth_service.py](../app/users/tests/test_auth_service.py) | Login (tokens + `exp`, password incorrecta, usuario inexistente o inactivo, campos faltantes, body sin JSON:API), registro (crea con `role='user'` y password hasheada, no expone la password, username/email repetidos dan 409, validaciones del serializer con `source.pointer`), `me` (perfil, 401 sin auth) y un **flujo JWT completo contra las URLs reales** con `APIClient`: login → `/me` con el access → `token/refresh` → `/me` con el access nuevo, más tokens inválidos y usar el access como refresh |

A diferencia del resto, la clase `TestFlujoJWTCompleto` no usa la fixture `call` sino `APIClient` contra las rutas reales: es la única forma de ejercitar `JWTAuthentication` y la vista de simplejwt (`token/refresh`), que no pasan por los servicios del proyecto.

## 4.4. Quinta tanda (Workload, 26 tests)

| Archivo | Qué cubre |
|---|---|
| [test_workload_service.py](../app/organizations/tests/test_workload_service.py) | `clasificar` (bordes del umbral, que es inclusivo), panel (owner/admin/group lead sí; contributor, member y lead de **otro** grupo no; solo cuentan tareas `pending`/`in_progress`; **carga global** sumando tareas de otros grupos; tarea con varios asignados; cambiar el umbral reclasifica), detalle de un miembro (tareas activas de otros grupos con su `group_id`/`project_id`), y `advertencias_de_asignacion` llamada directo (sin advertencia si no hay sobrecarga, alternativas solo `available`, nunca sugiere a los propios asignados, ignora ids fuera del grupo, máximo 3) |

La fixture `wl` arma una org con umbral 3 y dos grupos (Backend y Frontend) donde un mismo contributor participa en ambos, para poder testear la carga global.

## 5. Notas sobre el estado actual

- **Queda sin testear solo el seed** de `organizations` (`seed_service`), que existe únicamente con `DEBUG=True`.
- No se integró un reporte de cobertura (`pytest-cov`) — se puede sumar después sin fricción si hace falta medir qué porcentaje del código está cubierto.
- No hay CI (GitHub Actions ni similar) corriendo esta suite automáticamente en cada push/PR — corre solo localmente por ahora.
