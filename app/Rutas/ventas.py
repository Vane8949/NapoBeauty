from django.shortcuts import render

def panel_ventas(request):
    return render(request, 'ventas/index.html')