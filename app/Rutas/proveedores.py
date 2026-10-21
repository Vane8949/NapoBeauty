from django.shortcuts import render

def panel_proveedores(request):
    return render(request, 'proveedores/index.html')