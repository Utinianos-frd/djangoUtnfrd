from rest_framework.decorators import api_view
from django.http import JsonResponse
from ..services.auth_service import login_usuario

@api_view(['POST'])
def login(request):
    resultado = login_usuario(request)
    return JsonResponse(resultado)

@api_view(['POST'])
def register(request):
    return JsonResponse({"ok": False, "message": "Registro no implementado aún"})

