from django.shortcuts import render

def panel_inventario(request):
    return render(request, 'inventario/index.html')