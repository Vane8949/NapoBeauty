"""Carga datos de ejemplo para probar el panel.

Uso:  python manage.py cargar_datos_ejemplo

Crea proveedores, productos (con su compra inicial de stock), clientes, dos usuarios,
ventas, devoluciones y reseñas. Solo se ejecuta si todavía no hay productos ni ventas.
Ojo: en Napo Beauty nada se borra, así que estos datos solo se pueden deshabilitar.
"""
import secrets
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from app.models import (
    Categoria, Cliente, Compra, DetalleCompra, DetalleDevolucion, DetalleVenta, Devolucion, DireccionCliente,
    Marca, MetodoPago, MovimientoInventario, MovimientoPuntos, Producto, Proveedor, Resena, Rol, Usuario, VarianteProducto,
    Venta,
)
from app.servicios import ajustar_puntos, registrar_movimiento, sincronizar_producto, variante_unica

PROVEEDORES = [
    ('Distribuidora Belleza Total', 'J0310000012345', 'Carlos Mendoza', '+505 2250-1122', 'ventas@bellezatotal.com.ni',
     'Km 5 Carretera a Masaya, Managua'),
    ('Cosméticos del Pacífico', 'J0310000067890', 'Andrea Rivas', '+505 2311-4455', 'pedidos@cospacifico.com.ni',
     'Barrio San Felipe, León'),
    ('Importadora Glamour', 'J0310000024680', 'Roberto Chávez', '+505 2278-9900', 'contacto@glamour.com.ni',
     'Altamira, Managua'),
]

# sku, nombre, subcategoría, marca, proveedor (índice), compra, venta, stock inicial, stock mínimo
PRODUCTOS = [
    ('NAP-001', 'SuperStay Matte Ink', 'Labios', 'Maybelline', 0, 110, 180, 50, 10),
    ('NAP-002', 'Gloss Bomb', 'Labios', 'Fenty Beauty', 1, 300, 450, 18, 5),
    ('NAP-003', 'Soft Pinch Liquid Blush', 'Rostro', 'Rare Beauty', 1, 280, 430, 6, 5),
    ('NAP-004', 'Sky High Máscara', 'Ojos', 'Maybelline', 0, 160, 250, 35, 8),
    ('NAP-005', 'Elixir Ultime Aceite Capilar', 'Aceites y serums', 'Kérastase', 2, 900, 1350, 6, 3),
    ('NAP-006', 'Set de brochas Everyday Essentials', 'Brochas', 'Real Techniques', 2, 160, 250, 12, 4),
    ('NAP-007', 'Hyaluronic Acid 2% + B5', 'Serums', 'The Ordinary', 2, 180, 280, 0, 5),
    ('NAP-008', 'Esponja Miracle Complexion', 'Esponjas', 'Real Techniques', 2, 90, 150, 25, 5),
    ('NAP-009', 'Fit Me Base Líquida', 'Rostro', 'Maybelline', 0, 170, 260, 20, 6),
    ('NAP-010', 'Niacinamide 10% + Zinc 1%', 'Serums', 'The Ordinary', 2, 170, 270, 15, 5),
]

# Productos con varios tonos, cada uno con su stock: sku -> [(tono, color, stock, mínimo)]
# (la suma de los tonos es el stock de PRODUCTOS)
TONOS = {
    'NAP-001': [('Pioneer', '#9B1B30', 20, 4), ('Lover', '#C2185B', 18, 4), ('Seductress', '#B5656B', 12, 4)],
    'NAP-009': [('120 Classic Ivory', '#E8C8A8', 9, 2), ('220 Natural Beige', '#D2A57E', 9, 2),
                ('330 Toffee', '#A86E4A', 2, 3)],
}

CLIENTES = [
    ('Ana', 'García', 'ana.garcia@email.com', '+505 8888-1234', date(1996, 3, 14)),
    ('Daniela', 'Pérez', 'daniela.perez@email.com', '+505 8777-5678', date(1999, 8, 2)),
    ('Sofía', 'Martínez', 'sofia.martinez@email.com', '+505 8555-2468', None),
    ('Lucía', 'Torres', None, '+505 8444-1357', None),          # cliente de mostrador, sin correo
]

# factura, canal, cliente (índice o None), método, días atrás, estado, [(producto índice, cantidad)], envío
VENTAS = [
    ('V-000001', 'Tienda', 0, 'Efectivo', 9, 'Entregado', [(0, 2), (3, 1)], 0),
    ('V-000002', 'En linea', 1, 'Tarjeta', 6, 'En camino', [(1, 1), (2, 1)], 100),
    ('V-000003', 'Tienda', None, 'Efectivo', 4, 'Entregado', [(5, 1)], 0),
    ('V-000004', 'Tienda', 2, 'Transferencia', 2, 'Pagada', [(8, 1), (7, 2)], 0),
    ('V-000005', 'En linea', 0, 'Tarjeta', 1, 'Pendiente', [(4, 1)], 100),
    ('V-000006', 'Tienda', 3, 'Efectivo', 0, 'Entregado', [(9, 1), (0, 1)], 0),
]


class Command(BaseCommand):
    help = 'Carga datos de ejemplo (productos, clientes, ventas...) para probar el panel.'

    def handle(self, *args, **options):
        if Producto.objects.exists() or Venta.objects.exists():
            raise CommandError('La base ya tiene productos o ventas: no se cargan datos de ejemplo.')
        try:
            rol_admin = Rol.objects.get(nombre='Administrador')
            rol_cajero = Rol.objects.get(nombre='Vendedor/Cajero')
        except Rol.DoesNotExist:
            raise CommandError('Faltan los roles. Ejecuta primero database/napobeauty_sqlserver.sql.')

        with transaction.atomic():
            contrasenas = self.crear_usuarios(rol_admin, rol_cajero)
            admin = Usuario.objects.get(nombre_usuario='admin')
            proveedores = self.crear_proveedores()
            productos = self.crear_productos(proveedores, admin)
            clientes = self.crear_clientes()
            ventas = self.crear_ventas(productos, clientes, admin)
            self.crear_devoluciones(ventas, admin)
            self.crear_resenas(productos, clientes)

        self.stdout.write(self.style.SUCCESS(
            f'Listo: {len(proveedores)} proveedores, {len(productos)} productos, {len(clientes)} clientes, '
            f'{len(ventas)} ventas y 2 devoluciones.'))
        if contrasenas:
            self.stdout.write('\nUsuarios creados (guarda estas contraseñas, no se vuelven a mostrar):')
            for usuario, contrasena in contrasenas:
                self.stdout.write(f'  {usuario:<8} {contrasena}')

    # ------------------------------------------------------------------
    def crear_usuarios(self, rol_admin, rol_cajero):
        creados = []
        for usuario, nombre, apellido, correo, rol in [
            ('admin', 'Administrador', 'Napo Beauty', 'admin@napobeauty.com', rol_admin),
            ('caja1', 'María', 'López', 'caja1@napobeauty.com', rol_cajero),
        ]:
            if Usuario.objects.filter(nombre_usuario=usuario).exists():
                continue
            contrasena = secrets.token_urlsafe(9)
            Usuario.objects.create(rol=rol, nombre=nombre, apellido=apellido, nombre_usuario=usuario,
                                   correo=correo, contrasena_hash=make_password(contrasena))
            creados.append((usuario, contrasena))
        return creados

    def crear_proveedores(self):
        return [
            Proveedor.objects.create(nombre_empresa=empresa, ruc=ruc, nombre_contacto=contacto, telefono=telefono,
                                     correo=correo, direccion=direccion)
            for empresa, ruc, contacto, telefono, correo, direccion in PROVEEDORES
        ]

    def crear_productos(self, proveedores, admin):
        productos = []
        compras = {}
        for sku, nombre, sub, marca, prov, compra, venta, stock, minimo in PRODUCTOS:
            producto = Producto.objects.create(
                sku=sku, nombre=nombre, categoria=Categoria.objects.get(nombre=sub, categoria_padre__isnull=False),
                marca=Marca.objects.get_or_create(nombre=marca)[0], proveedor=proveedores[prov],
                precio_compra=Decimal(compra), precio_venta=Decimal(venta), stock_minimo=minimo,
                descripcion=f'{marca} {nombre}. Producto original importado.',
            )
            productos.append(producto)
            if sku in TONOS:
                entradas = [(VarianteProducto.objects.create(producto=producto, nombre=tono, color_hex=color,
                                                             stock_minimo=minimo, orden=orden), cantidad)
                            for orden, (tono, color, cantidad, minimo) in enumerate(TONOS[sku])]
                sincronizar_producto(producto.pk)
            else:
                entradas = [(variante_unica(producto), stock)]
            for variante, cantidad in entradas:
                if not cantidad:
                    continue
                # El stock inicial entra con una compra recibida al proveedor
                if prov not in compras:
                    compras[prov] = Compra.objects.create(
                        proveedor=proveedores[prov], usuario=admin, numero_factura=f'FP-{1000 + prov}',
                        fecha=timezone.now() - timedelta(days=15), estado=Compra.Estado.RECIBIDA)
                DetalleCompra.objects.create(compra=compras[prov], producto=producto, variante=variante,
                                             cantidad=cantidad, costo_unitario=Decimal(compra))
                registrar_movimiento(variante, MovimientoInventario.Tipo.ENTRADA, cantidad, usuario=admin,
                                     motivo='Compra inicial', tipo_referencia='Compra',
                                     referencia_id=compras[prov].pk)
        for compra in compras.values():
            compra.total = sum(d.cantidad * d.costo_unitario for d in compra.detalles.all())
            compra.save(update_fields=['total'])
        # Una orden de compra pendiente para que se vea en Proveedores
        Compra.objects.create(proveedor=proveedores[2], usuario=admin, numero_factura='FP-2001',
                              estado=Compra.Estado.PENDIENTE, total=Decimal('5400.00'),
                              observaciones='Reposición de serums The Ordinary')
        return productos

    def crear_clientes(self):
        clientes = []
        for nombre, apellido, correo, telefono, nacimiento in CLIENTES:
            cliente = Cliente.objects.create(nombre=nombre, apellido=apellido, correo=correo, telefono=telefono,
                                             fecha_nacimiento=nacimiento)
            if correo:
                DireccionCliente.objects.create(
                    cliente=cliente, alias='Casa', nombre_recibe=f'{nombre} {apellido}', telefono=telefono,
                    departamento='Managua', municipio='Managua',
                    direccion_exacta='De la Rotonda Rubén Darío 2 c. al sur, casa 15', es_predeterminada=True)
            clientes.append(cliente)
        return clientes

    def crear_ventas(self, productos, clientes, admin):
        ventas = []
        for factura, canal, cli, metodo, dias, estado, lineas, envio in VENTAS:
            cliente = clientes[cli] if cli is not None else None
            direccion = cliente.direcciones.first() if (cliente and canal == 'En linea') else None
            subtotal = sum(productos[i].precio_venta * cantidad for i, cantidad in lineas)
            puntos = int(subtotal // 10) if cliente else 0          # 1 punto por cada C$ 10
            venta = Venta.objects.create(
                numero_factura=factura, canal=canal, cliente=cliente, usuario=admin if canal == 'Tienda' else None,
                metodo_pago=MetodoPago.objects.get(nombre=metodo), direccion_cliente=direccion,
                direccion_envio=str(direccion) if direccion else None,
                fecha=timezone.now() - timedelta(days=dias, hours=dias), subtotal=subtotal,
                costo_envio=Decimal(envio), estado=estado, puntos_ganados=puntos,
            )
            for i, cantidad in lineas:
                variante = productos[i].variantes.order_by('-stock_actual', 'orden').first()   # el tono con más stock
                DetalleVenta.objects.create(venta=venta, producto=productos[i], variante=variante, cantidad=cantidad,
                                            precio_unitario=productos[i].precio_venta)
                registrar_movimiento(variante, MovimientoInventario.Tipo.SALIDA, -cantidad, usuario=admin,
                                     motivo=f'Venta {factura}', tipo_referencia='Venta', referencia_id=venta.pk)
            if cliente:
                ajustar_puntos(cliente, puntos, MovimientoPuntos.Tipo.GANADOS, venta=venta,
                               descripcion=f'Compra {factura}')
            ventas.append(venta)
        return ventas

    def crear_devoluciones(self, ventas, admin):
        primera = Devolucion.objects.create(
            venta=ventas[0], motivo=Devolucion.Motivo.DEFECTO, tipo_resolucion=Devolucion.TipoResolucion.CAMBIO,
            descripcion='El labial llegó con la tapa quebrada.')
        DetalleDevolucion.objects.create(devolucion=primera, detalle_venta=ventas[0].detalles.first(), cantidad=1)

        segunda = Devolucion.objects.create(
            venta=ventas[3], motivo=Devolucion.Motivo.EXPECTATIVAS,
            tipo_resolucion=Devolucion.TipoResolucion.REEMBOLSO, estado=Devolucion.Estado.APROBADA,
            monto_reembolso=Decimal('150.00'), usuario=admin, fecha_resolucion=timezone.now(),
            descripcion='La clienta prefiere otro tipo de esponja. Producto sellado.')
        DetalleDevolucion.objects.create(devolucion=segunda, detalle_venta=ventas[3].detalles.last(), cantidad=1,
                                         regresa_a_inventario=True)

    def crear_resenas(self, productos, clientes):
        for producto, cliente, estrellas, comentario in [
            (productos[0], clientes[0], 5, 'Dura todo el día y no reseca.'),
            (productos[0], clientes[3], 4, 'Muy buen color.'),
            (productos[1], clientes[1], 5, 'Brilla precioso.'),
            (productos[2], clientes[1], 4, None),
        ]:
            Resena.objects.create(producto=producto, cliente=cliente, calificacion=estrellas, comentario=comentario)
