from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views.auth_view import login, register, me

urlpatterns = [
    path('login', login, name='login'),
    path('register', register, name='register'),
    path('token/refresh', TokenRefreshView.as_view(), name='token_refresh'),
    path('me', me, name='me'),
]
