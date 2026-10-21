from django.shortcuts import render

def panel_reportes(request):
    return render(request, 'reportes/index.html')