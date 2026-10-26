from django.urls import path
from .Rutas import dashboard, productos, inventario, ventas, devoluciones, clientes, proveedores, reportes, usuarios, configuracion, auth

urlpatterns = [
    # Ahora la ruta principal o raíz ('') te enviará directo al Login
    path('', auth.login_view, name='login'),
    
    # El Dashboard pasa a tener su propia ruta específica
    path('dashboard/', dashboard.panel_principal, name='dashboard'),
    
    # El resto de módulos se mantiene igual
    path('productos/', productos.panel_productos, name='productos'),
    path('inventario/', inventario.panel_inventario, name='inventario'),
    path('ventas/', ventas.panel_ventas, name='ventas'),
    path('devoluciones/', devoluciones.panel_devoluciones, name='devoluciones'),
    path('clientes/', clientes.panel_clientes, name='clientes'),
    path('proveedores/', proveedores.panel_proveedores, name='proveedores'),
    path('reportes/', reportes.panel_reportes, name='reportes'),
    path('usuarios/', usuarios.panel_usuarios, name='usuarios'),
    path('configuracion/', configuracion.panel_configuracion, name='configuracion'),
]