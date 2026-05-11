from django.http import JsonResponse
from ..services.auth_service import login_usuario

def login(request):
    resultado = login_usuario(request)
    return JsonResponse(resultado)