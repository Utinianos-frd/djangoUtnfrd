from django.urls import path
from .views.auth_view import login


urlpatterns = [
    path('', login, name='login'),
]
