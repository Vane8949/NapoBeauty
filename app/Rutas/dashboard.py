from django.shortcuts import render

def panel_principal(request):
    return render(request, 'dashboard/index.html')