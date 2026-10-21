from django.urls import path
from .Rutas import dashboard, productos, inventario

urlpatterns = [
    path('', dashboard.panel_principal, name='dashboard'),
    path('productos/', productos.panel_productos, name='productos'),
    path('inventario/', inventario.panel_inventario, name='inventario'),
]