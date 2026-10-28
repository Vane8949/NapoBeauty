from django.urls import include, path
from .Rutas import (dashboard, productos, inventario, ventas, devoluciones, devoluciones_proveedor, clientes, proveedores,
                    reportes, usuarios, configuracion, auth)

urlpatterns = [
    # Ahora la ruta principal o raíz ('') te enviará directo al Login
    path('', auth.login_view, name='login'),

    # El Dashboard pasa a tener su propia ruta específica
    path('dashboard/', dashboard.panel_principal, name='dashboard'),

    # Productos
    path('productos/', productos.panel_productos, name='productos'),
    path('productos/nuevo/', productos.crear_producto, name='producto_crear'),
    path('productos/<int:pk>/', productos.detalle_producto, name='producto_detalle'),
    path('productos/<int:pk>/editar/', productos.editar_producto, name='producto_editar'),
    path('productos/<int:pk>/unir-tono/', productos.unir_tono, name='producto_unir_tono'),

    # Inventario (el "editar" de inventario es ajustar el stock)
    path('inventario/', inventario.panel_inventario, name='inventario'),
    path('inventario/movimientos/', inventario.movimientos_inventario, name='inventario_movimientos'),
    path('inventario/ajustar/', inventario.ajustar_inventario, name='inventario_ajustar_elegir'),
    path('inventario/<int:pk>/', inventario.detalle_inventario, name='inventario_detalle'),
    path('inventario/<int:pk>/ajustar/', inventario.ajustar_inventario, name='inventario_ajustar'),

    # Ventas
    path('ventas/', ventas.panel_ventas, name='ventas'),
    path('ventas/nueva/', ventas.crear_venta, name='venta_crear'),
    path('ventas/<int:pk>/', ventas.detalle_venta, name='venta_detalle'),
    path('ventas/<int:pk>/editar/', ventas.editar_venta, name='venta_editar'),
    path('ventas/<int:pk>/recibo/', ventas.recibo_venta, name='venta_recibo'),

    # Devoluciones
    path('devoluciones/', devoluciones.panel_devoluciones, name='devoluciones'),
    path('devoluciones/nueva/', devoluciones.crear_devolucion, name='devolucion_crear'),
    path('devoluciones/<int:pk>/', devoluciones.detalle_devolucion, name='devolucion_detalle'),
    path('devoluciones/<int:pk>/editar/', devoluciones.editar_devolucion, name='devolucion_editar'),
    # Devoluciones a proveedores (productos que la tienda le regresa al proveedor)
    path('devoluciones/proveedores/', devoluciones_proveedor.panel_devoluciones_proveedor, name='devoluciones_proveedor'),
    path('devoluciones/proveedores/nueva/', devoluciones_proveedor.crear_devolucion_proveedor,
         name='devolucion_proveedor_crear'),
    path('devoluciones/proveedores/<int:pk>/', devoluciones_proveedor.detalle_devolucion_proveedor,
         name='devolucion_proveedor_detalle'),
    path('devoluciones/proveedores/<int:pk>/editar/', devoluciones_proveedor.editar_devolucion_proveedor,
         name='devolucion_proveedor_editar'),

    # Clientes
    path('clientes/', clientes.panel_clientes, name='clientes'),
    path('clientes/nuevo/', clientes.crear_cliente, name='cliente_crear'),
    path('clientes/<int:pk>/', clientes.detalle_cliente, name='cliente_detalle'),
    path('clientes/<int:pk>/editar/', clientes.editar_cliente, name='cliente_editar'),

    # Proveedores
    path('proveedores/', proveedores.panel_proveedores, name='proveedores'),
    path('proveedores/nuevo/', proveedores.crear_proveedor, name='proveedor_crear'),
    path('proveedores/<int:pk>/', proveedores.detalle_proveedor, name='proveedor_detalle'),
    path('proveedores/<int:pk>/editar/', proveedores.editar_proveedor, name='proveedor_editar'),

    # Usuarios
    path('usuarios/', usuarios.panel_usuarios, name='usuarios'),
    path('usuarios/nuevo/', usuarios.crear_usuario, name='usuario_crear'),
    path('usuarios/<int:pk>/', usuarios.detalle_usuario, name='usuario_detalle'),
    path('usuarios/<int:pk>/editar/', usuarios.editar_usuario, name='usuario_editar'),

    path('reportes/', reportes.panel_reportes, name='reportes'),
    path('configuracion/', configuracion.panel_configuracion, name='configuracion'),

    # ===== Vista cliente (tienda) -> app/Rutas/cliente/urls.py =====
    path('cliente/', include('app.Rutas.cliente.urls')),
]
