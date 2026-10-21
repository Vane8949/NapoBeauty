from django.urls import path
from .Rutas import dashboard, productos

urlpatterns = [
    path('', dashboard.panel_principal, name='dashboard'),
    path('productos/', productos.panel_productos, name='productos'),
]