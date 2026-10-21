from django.shortcuts import render

def panel_clientes(request):
    return render(request, 'clientes/index.html')