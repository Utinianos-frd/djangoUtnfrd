# Pruebas unitarias

Spec de la infraestructura de testing del proyecto y las convenciones para escribir tests nuevos. No es un requerimiento del documento de especificación de Tasker — es tooling de calidad interna, pero se documenta igual siguiendo la práctica ya establecida de este repo (un spec por cada pieza nueva).

> Primera tanda: 59 tests cubriendo `app/organizations` completo (Organization, Membership, Group, GroupMembership), corridos contra una base Postgres real de test. `app/users`, `app/tasks` y `app/focus` quedan sin tests todavía — ver sección 5.

## 1. Stack elegido

- **pytest + pytest-django** (no `unittest`/`manage.py test`). Se prefirió por la sintaxis de fixtures y `assert` simple sobre el estilo `TestCase`/`self.assertEqual` de Django — decisión explícita del usuario, discutida antes de empezar a escribir código.
- Dependencias nuevas en [requirements.txt](../requirements.txt): `pytest==9.1.1`, `pytest-django==4.14.0`.
- Configuración en [pytest.ini](../pytest.ini) (raíz del repo): apunta `DJANGO_SETTINGS_MODULE` a `config.settings` y restringe la búsqueda de tests a `app/`.

## 2. Cómo correrlos

```bash
python -m pytest                          # toda la suite
python -m pytest app/organizations -v     # solo una app, verbose
bash commands/dev.sh test                 # atajo (ver commands/dev.sh)
bash commands/dev.sh test app/organizations -v
```

`pytest-django` crea una base de datos de test aparte (`test_<nombre de la DB real>`) contra el mismo servidor Postgres de `docker-compose`, corre todo ahí, y la destruye al terminar — **nunca toca los datos de la base de desarrollo real**. Cada test individual corre dentro de una transacción que se revierte sola al final (gracias a `pytest.mark.django_db`), así que no hace falta limpiar nada a mano como sí había que hacer en los smoke tests manuales de las tandas anteriores.

## 3. Estructura y convenciones

- **Un paquete `tests/` por app** (`app/organizations/tests/`, y así para cada app a medida que se le sumen tests), no una carpeta `tests/` centralizada — mismo criterio modular que ya se usa con `services/`, `views/`, `serializers/` por app.
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

## 5. Notas sobre el estado actual

- **`app/users`, `app/tasks` y `app/focus` no tienen tests todavía** — es deliberadamente el alcance de esta primera tanda (se discutió explícitamente arrancar por `organizations`, que es donde más lógica de negocio hay). Quedan como trabajo pendiente para sesiones siguientes.
- No hay tests de las dependencias entre tareas (detección de ciclos) ni de Modo Foco (máquina de estados del pomodoro, gate de plan Pro) todavía, pese a ser la lógica más propensa a bugs sutiles del proyecto — son los candidatos más valiosos para la próxima tanda.
- No se integró un reporte de cobertura (`pytest-cov`) — se puede sumar después sin fricción si hace falta medir qué porcentaje del código está cubierto.
- No hay CI (GitHub Actions ni similar) corriendo esta suite automáticamente en cada push/PR — corre solo localmente por ahora.
