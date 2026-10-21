from django.shortcuts import render

def panel_usuarios(request):
    return render(request, 'usuarios/index.html')