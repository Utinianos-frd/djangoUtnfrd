from django.contrib.auth import authenticate, login


def login_usuario(request):

    username = request.POST.get('username')
    password = request.POST.get('password')

    user = authenticate(request, username=username, password=password)

    if not user:
        return {
            "ok": False,
            "message": "Invalid credentials"
        }

    login(request, user)
    return {
        "ok": True,
        "message": "Login successful"
    }

def auth_register(request):
    
    

    return {
        "ok": False,
        "message": "Registro no implementado aún"
    }