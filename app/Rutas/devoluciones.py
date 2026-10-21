from django.shortcuts import render

def panel_devoluciones(request):
    return render(request, 'devoluciones/index.html')