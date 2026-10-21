from django.shortcuts import render

def panel_productos(request):
    return render(request, 'productos/index.html')