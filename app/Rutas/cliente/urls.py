"""Rutas de la vista cliente. Se incluyen en app/urls.py bajo el prefijo /cliente/.

En las plantillas se usan con el espacio de nombres: {% url 'cliente:mi_cuenta' %}
"""
from django.urls import path

from . import cuenta

app_name = 'cliente'

urlpatterns = [
    path('cuenta/', cuenta.mi_cuenta, name='mi_cuenta'),
]
