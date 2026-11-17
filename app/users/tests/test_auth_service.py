import pytest
from rest_framework.test import APIClient

from app.users.models import Users
from app.users.views.auth_view import login, register, me

pytestmark = pytest.mark.django_db


def _login_payload(**attrs):
    return {"data": {"type": "sessions", "attributes": attrs}}


def _register_payload(**attrs):
    return {"data": {"type": "users", "attributes": attrs}}


class TestLogin:

    def test_credenciales_validas_devuelven_tokens(self, call, make_user):
        make_user('alex', password='secret123')

        status, data = call(login, 'post', '/', data=_login_payload(username='alex', password='secret123'))

        assert status == 200
        attributes = data['data']['attributes']
        assert attributes['access'] and attributes['refresh']
        assert attributes['exp'].endswith('Z')

    def test_password_incorrecta_da_401(self, call, make_user):
        make_user('alex', password='secret123')

        status, data = call(login, 'post', '/', data=_login_payload(username='alex', password='otra'))

        assert status == 401
        assert 'access' not in str(data)

    def test_usuario_inexistente_da_401(self, call):
        status, _data = call(login, 'post', '/', data=_login_payload(username='nadie', password='secret123'))

        assert status == 401

    def test_usuario_inactivo_no_puede_loguearse(self, call, make_user):
        make_user('alex', password='secret123', is_active=False)

        status, _data = call(login, 'post', '/', data=_login_payload(username='alex', password='secret123'))

        assert status == 401

    @pytest.mark.parametrize('attrs', [{'username': 'alex'}, {'password': 'secret123'}, {}])
    def test_faltan_campos_da_400(self, call, attrs):
        status, _data = call(login, 'post', '/', data=_login_payload(**attrs))

        assert status == 400

    def test_body_sin_formato_jsonapi_da_400(self, call):
        status, _data = call(login, 'post', '/', data={'username': 'alex', 'password': 'secret123'})

        assert status == 400


class TestRegistro:

    def test_crea_usuario_y_devuelve_tokens(self, call):
        status, data = call(
            register, 'post', '/',
            data=_register_payload(username='alex', email='alex@example.com', password='secret123'),
        )

        assert status == 201
        assert data['data']['attributes']['access'] and data['data']['attributes']['refresh']
        user = Users.objects.get(username='alex')
        assert user.email == 'alex@example.com'
        assert user.role == 'user'
        assert user.check_password('secret123')
        assert user.password != 'secret123'  # se guarda hasheada

    def test_la_respuesta_no_expone_la_password(self, call):
        _status, data = call(
            register, 'post', '/',
            data=_register_payload(username='alex', email='alex@example.com', password='secret123'),
        )

        assert 'secret123' not in str(data)

    def test_username_repetido_da_409(self, call, make_user):
        make_user('alex')

        status, data = call(
            register, 'post', '/',
            data=_register_payload(username='alex', email='otro@example.com', password='secret123'),
        )

        assert status == 409
        assert 'username' in data['errors'][0]['detail']

    def test_email_repetido_da_409(self, call, make_user):
        make_user('alex', email='alex@example.com')

        status, data = call(
            register, 'post', '/',
            data=_register_payload(username='otro', email='alex@example.com', password='secret123'),
        )

        assert status == 409
        assert 'email' in data['errors'][0]['detail']

    @pytest.mark.parametrize('field, attrs', [
        ('password', {'username': 'alex', 'email': 'alex@example.com', 'password': 'corta'}),
        ('email', {'username': 'alex', 'email': 'no-es-un-email', 'password': 'secret123'}),
        ('username', {'email': 'alex@example.com', 'password': 'secret123'}),
    ])
    def test_validaciones_del_serializer_dan_400_con_pointer(self, call, field, attrs):
        status, data = call(register, 'post', '/', data=_register_payload(**attrs))

        assert status == 400
        assert data['errors'][0]['source']['pointer'] == f'/data/attributes/{field}'
        assert not Users.objects.exists()

    def test_body_sin_formato_jsonapi_da_400(self, call):
        status, _data = call(register, 'post', '/', data={'username': 'alex'})

        assert status == 400


class TestMe:

    def test_devuelve_el_perfil_del_usuario_autenticado(self, call, make_user):
        user = make_user('alex', email='alex@example.com')

        status, data = call(me, 'get', '/', user)

        assert status == 200
        assert data['data']['id'] == str(user.id)
        assert data['data']['attributes'] == {
            'username': 'alex', 'email': 'alex@example.com', 'role': 'user',
            'first_name': '', 'last_name': '', 'age': None, 'phone': '', 'bio': '', 'avatar_url': '',
        }

    def test_sin_autenticar_da_401(self, call):
        status, _data = call(me, 'get', '/')

        assert status == 401


class TestFlujoJWTCompleto:
    """Contra las URLs reales con APIClient: login -> /me con el access -> refresh -> /me con el access nuevo."""

    def test_login_me_y_refresh(self, make_user):
        make_user('alex', password='secret123')
        client = APIClient()

        login_response = client.post(
            '/api/v1/auth/login', _login_payload(username='alex', password='secret123'), format='json',
        )
        tokens = login_response.data['data']['attributes']

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        assert client.get('/api/v1/auth/me').status_code == 200

        client.credentials()
        refresh_response = client.post('/api/v1/auth/token/refresh', {'refresh': tokens['refresh']}, format='json')
        assert refresh_response.status_code == 200
        new_access = refresh_response.data['access']

        client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_access}')
        me_response = client.get('/api/v1/auth/me')
        assert me_response.status_code == 200
        assert me_response.data['data']['attributes']['username'] == 'alex'

    def test_access_token_invalido_da_401(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer no-es-un-jwt')

        assert client.get('/api/v1/auth/me').status_code == 401

    def test_refresh_token_invalido_da_401(self):
        response = APIClient().post('/api/v1/auth/token/refresh', {'refresh': 'no-es-un-jwt'}, format='json')

        assert response.status_code == 401

    def test_no_se_puede_usar_el_access_como_refresh(self, make_user):
        make_user('alex', password='secret123')
        client = APIClient()
        tokens = client.post(
            '/api/v1/auth/login', _login_payload(username='alex', password='secret123'), format='json',
        ).data['data']['attributes']

        response = client.post('/api/v1/auth/token/refresh', {'refresh': tokens['access']}, format='json')

        assert response.status_code == 401
