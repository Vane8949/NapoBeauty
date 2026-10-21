from django.urls import path
from .Rutas import dashboard, productos, inventario, ventas, devoluciones, clientes, proveedores, reportes, usuarios

urlpatterns = [
    path('', dashboard.panel_principal, name='dashboard'),
    path('productos/', productos.panel_productos, name='productos'),
    path('inventario/', inventario.panel_inventario, name='inventario'),
    path('ventas/', ventas.panel_ventas, name='ventas'),
    path('devoluciones/', devoluciones.panel_devoluciones, name='devoluciones'),
    path('clientes/', clientes.panel_clientes, name='clientes'),
    path('proveedores/', proveedores.panel_proveedores, name='proveedores'),
    path('reportes/', reportes.panel_reportes, name='reportes'),
    path('usuarios/', usuarios.panel_usuarios, name='usuarios'),
]