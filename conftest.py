import pytest
from rest_framework.test import APIRequestFactory, force_authenticate


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    """Hasher MD5 solo en tests: el PBKDF2 por defecto es lento a propósito y cada test crea varios usuarios."""
    settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


@pytest.fixture
def rf():
    """APIRequestFactory — building block para armar requests autenticados contra las vistas."""
    return APIRequestFactory()


@pytest.fixture
def call(rf):
    """Invoca una vista (los wrappers finos de app/*/views/) como si fuera una request HTTP real,
    sin pasar por el urlconf. Devuelve (status_code, data). Mismo patrón que se usó en los smoke
    tests manuales de este proyecto antes de que existiera esta suite."""

    def _call(view, method, path, user=None, data=None, **url_kwargs):
        request = getattr(rf, method)(path, data, format='json')
        if user is not None:
            force_authenticate(request, user=user)
        response = view(request, **url_kwargs)
        return response.status_code, response.data

    return _call


@pytest.fixture
def make_user(db):
    """Factory de Users.objects.create_user con defaults razonables y username único por llamada."""
    from app.users.models import Users

    state = {'count': 0}

    def _make_user(username=None, password='pass1234', **extra):
        state['count'] += 1
        username = username or f'user{state["count"]}'
        extra.setdefault('email', f'{username}@test.com')
        extra.setdefault('role', 'user')
        return Users.objects.create_user(username=username, password=password, **extra)

    return _make_user
