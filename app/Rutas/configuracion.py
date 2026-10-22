from django.shortcuts import render

def panel_configuracion(request):
    return render(request, 'configuracion/index.html')