"""Reglas del negocio que tocan varias tablas a la vez.

El stock vive en cada variante (tono) del producto; Producto.StockActual es la suma.
Todo cambio de stock pasa por registrar_movimiento(): actualiza la variante y el total
del producto y deja la huella en MovimientoInventario dentro de la misma transacción.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from app.models import (
    Cliente, DetalleCompra, DetalleDevolucion, DetalleDevolucionProveedor, DetalleVenta, Devolucion,
    DevolucionProveedor, MovimientoInventario, MovimientoPuntos, Producto, Resena, VarianteProducto, Venta,
)

PUNTOS_POR_CORDOBA = Decimal('0.1')     # 1 punto por cada C$ 10 de compra


class ErrorDeNegocio(Exception):
    """Operación no permitida por las reglas de Napo Beauty (el mensaje se muestra al usuario)."""


def variante_unica(producto):
    """La variante de un producto que no tiene tonos. Si aún no tiene ninguna, crea 'Único' con su stock."""
    variantes = list(producto.variantes.all()[:2])
    if len(variantes) == 1:
        return variantes[0]
    if not variantes:
        actual = Producto.objects.filter(pk=producto.pk).values('stock_actual', 'stock_minimo').get()
        return VarianteProducto.objects.create(producto_id=producto.pk, nombre=VarianteProducto.UNICA,
                                               stock_actual=actual['stock_actual'], stock_minimo=actual['stock_minimo'])
    raise ErrorDeNegocio(f'{producto.nombre} tiene varios tonos: elige cuál.')


def variante_de(item):
    """Variante de un renglón (venta, devolución a proveedor) o de un producto con un solo tono."""
    if isinstance(item, VarianteProducto):
        return item
    if isinstance(item, Producto):
        return variante_unica(item)
    return item.variante or variante_unica(item.producto)


def sincronizar_producto(producto_id):
    """Producto.StockActual = suma del stock de sus variantes; StockMinimo = suma de los mínimos activos."""
    variantes = VarianteProducto.objects.filter(producto_id=producto_id)
    stock = variantes.aggregate(t=Sum('stock_actual'))['t'] or 0
    minimo = variantes.filter(activo=True).aggregate(t=Sum('stock_minimo'))['t'] or 0
    Producto.objects.filter(pk=producto_id).update(stock_actual=stock, stock_minimo=minimo)


@transaction.atomic
def registrar_movimiento(item, tipo, cantidad, usuario=None, motivo=None,
                         tipo_referencia=None, referencia_id=None):
    """Suma (cantidad > 0) o resta (cantidad < 0) stock de una variante y guarda el movimiento.

    item: la variante (tono). Un Producto solo se acepta si tiene un único tono.
    Bloquea la fila de la variante mientras dura la transacción para que dos ajustes
    simultáneos no se pisen; el total del producto se actualiza en la misma transacción.
    """
    if cantidad == 0:
        raise ErrorDeNegocio('La cantidad del movimiento no puede ser cero.')

    variante = VarianteProducto.objects.select_for_update().select_related('producto').get(pk=variante_de(item).pk)
    anterior = variante.stock_actual
    nuevo = anterior + cantidad
    if nuevo < 0:
        raise ErrorDeNegocio(
            f'No hay suficiente stock de {variante}: hay {anterior} y se intentan sacar {-cantidad}.')

    variante.stock_actual = nuevo
    variante.save(update_fields=['stock_actual'])
    Producto.objects.filter(pk=variante.producto_id).update(stock_actual=F('stock_actual') + cantidad)
    return MovimientoInventario.objects.create(
        producto_id=variante.producto_id, variante=variante, usuario=usuario, tipo=tipo, cantidad=cantidad,
        stock_anterior=anterior, stock_nuevo=nuevo, motivo=motivo,
        tipo_referencia=tipo_referencia, referencia_id=referencia_id,
    )


@transaction.atomic
def guardar_stock_unico(producto, stock, stock_minimo, usuario=None, motivo='Ajuste desde Editar producto'):
    """Producto sin tonos: fija el stock y el mínimo de su variante 'Único'."""
    variante = variante_unica(producto)
    cambio = stock - variante.stock_actual
    if cambio:
        tipo = MovimientoInventario.Tipo.ENTRADA if motivo == 'Stock inicial' else MovimientoInventario.Tipo.AJUSTE
        registrar_movimiento(variante, tipo, cambio, usuario=usuario, motivo=motivo)
    VarianteProducto.objects.filter(pk=variante.pk).update(stock_minimo=stock_minimo)
    sincronizar_producto(producto.pk)


def _guardar_foto_tono(variante, archivo):
    """Guarda la foto del tono en media/productos/tonos/. La foto anterior queda en disco (nada se borra)."""
    variante.imagen.save(archivo.name, archivo, save=False)
    VarianteProducto.objects.filter(pk=variante.pk).update(imagen=variante.imagen.name)


@transaction.atomic
def guardar_tonos(producto, filas, usuario=None):
    """Crea o actualiza los tonos de un producto.

    filas: [{id, nombre, sku, imagen, stock, stock_minimo, activo}] (imagen: archivo subido o None).

    Un tono nuevo entra con un movimiento de Entrada; si cambia el stock de uno existente queda un Ajuste.
    Ningún tono se borra: el que no se vende más queda deshabilitado.
    """
    existentes = {v.pk: v for v in VarianteProducto.objects.select_for_update().filter(producto_id=producto.pk)}
    # Primero se renombran con un nombre temporal para que un intercambio de nombres no choque con la regla única
    renombrar = [existentes[f['id']] for f in filas if f['id'] and existentes[f['id']].nombre != f['nombre']]
    for variante in renombrar:
        VarianteProducto.objects.filter(pk=variante.pk).update(nombre=f'~{variante.pk}')
    # Igual con los SKU que cambian (también son únicos)
    cambian_sku = [f['id'] for f in filas if f['id'] and (existentes[f['id']].sku or None) != f.get('sku')]
    VarianteProducto.objects.filter(pk__in=cambian_sku).update(sku=None)
    for orden, fila in enumerate(filas):
        datos = {'nombre': fila['nombre'], 'sku': fila.get('sku'),
                 'stock_minimo': fila['stock_minimo'], 'orden': orden, 'activo': fila['activo']}
        variante = existentes.get(fila['id'])
        if variante is None:
            variante = VarianteProducto.objects.create(producto_id=producto.pk, **datos)
            if fila.get('imagen'):
                _guardar_foto_tono(variante, fila['imagen'])
            if fila['stock']:
                registrar_movimiento(variante, MovimientoInventario.Tipo.ENTRADA, fila['stock'], usuario=usuario,
                                     motivo='Stock inicial del tono')
            continue
        VarianteProducto.objects.filter(pk=variante.pk).update(**datos)
        if fila.get('imagen'):
            _guardar_foto_tono(variante, fila['imagen'])
        cambio = fila['stock'] - variante.stock_actual
        if cambio:
            registrar_movimiento(variante, MovimientoInventario.Tipo.AJUSTE, cambio, usuario=usuario,
                                 motivo='Ajuste desde Editar producto')
    sincronizar_producto(producto.pk)


@transaction.atomic
def ajustar_puntos(cliente, puntos, tipo, usuario=None, venta=None, recompensa=None, descripcion=None):
    """Suma o resta puntos al cliente y deja el movimiento en el historial."""
    if puntos == 0:
        return None
    cliente = Cliente.objects.select_for_update().get(pk=cliente.pk)
    # Si el cliente ya gastó parte de esos puntos, no se deja el saldo en negativo
    if cliente.puntos_disponibles + puntos < 0:
        puntos = -cliente.puntos_disponibles
        if puntos == 0:
            return None
    cliente.puntos_disponibles += puntos
    cliente.save(update_fields=['puntos_disponibles'])
    return MovimientoPuntos.objects.create(
        cliente=cliente, tipo=tipo, puntos=puntos, venta=venta, recompensa=recompensa, descripcion=descripcion,
    )


@transaction.atomic
def cambiar_estado_venta(venta, activa, usuario=None):
    """Anula (activa=False) o reactiva (activa=True) una venta.

    Anular devuelve al inventario los productos vendidos y quita los puntos que la
    venta le dio al cliente. Reactivar hace lo contrario. Nada se borra.
    """
    venta = Venta.objects.select_for_update().get(pk=venta.pk)
    if venta.activo == activa:
        return venta

    signo = -1 if activa else 1          # anular = devolver stock (+); reactivar = volver a sacar (-)
    accion = 'Reactivación' if activa else 'Anulación'
    for detalle in venta.detalles.select_related('producto', 'variante'):
        registrar_movimiento(
            variante_de(detalle), MovimientoInventario.Tipo.AJUSTE, signo * detalle.cantidad, usuario=usuario,
            motivo=f'{accion} de la venta {venta.numero_factura}', tipo_referencia='Venta', referencia_id=venta.pk,
        )

    if venta.cliente_id and venta.puntos_ganados:
        ajustar_puntos(
            venta.cliente, venta.puntos_ganados if activa else -venta.puntos_ganados,
            MovimientoPuntos.Tipo.AJUSTE, usuario=usuario, venta=venta,
            descripcion=f'{accion} de la venta {venta.numero_factura}',
        )

    venta.activo = activa
    venta.save(update_fields=['activo'])
    return venta


@transaction.atomic
def resolver_devolucion(devolucion, estado_anterior, usuario=None):
    """Se llama después de guardar una devolución con un estado nuevo.

    - Al dejar de estar Pendiente se registra quién la resolvió y cuándo.
    - Al pasar a Completada, cada producto va a su destino: los de "Regresa al stock" se suman
      al inventario, los de "Se devuelve al proveedor" generan una devolución a proveedor
      (una por proveedor) y los dados de baja no mueven nada.
    """
    if devolucion.estado == estado_anterior:
        return devolucion

    if estado_anterior == Devolucion.Estado.COMPLETADA:
        raise ErrorDeNegocio('Una devolución completada ya movió el inventario y no puede cambiar de estado.')

    campos = []
    if devolucion.estado != Devolucion.Estado.PENDIENTE:
        devolucion.fecha_resolucion = timezone.now()
        devolucion.usuario = usuario
        campos += ['fecha_resolucion', 'usuario']

    if devolucion.estado == Devolucion.Estado.COMPLETADA:
        al_proveedor = {}
        for detalle in devolucion.detalles.select_related('detalle_venta__producto__proveedor', 'detalle_venta__variante'):
            producto = detalle.detalle_venta.producto
            variante = variante_de(detalle.detalle_venta)
            if detalle.destino == DetalleDevolucion.Destino.INVENTARIO:
                registrar_movimiento(
                    variante, MovimientoInventario.Tipo.DEVOLUCION, detalle.cantidad,
                    usuario=usuario, motivo=f'Devolución #{devolucion.pk}',
                    tipo_referencia='Devolucion', referencia_id=devolucion.pk,
                )
            elif detalle.destino == DetalleDevolucion.Destino.PROVEEDOR:
                if producto.proveedor_id is None:
                    raise ErrorDeNegocio(f'{producto.nombre} no tiene proveedor asignado. Asígnaselo en Productos '
                                         f'para poder devolverlo al proveedor.')
                tonos = al_proveedor.setdefault(producto.proveedor, {})
                tonos[variante] = tonos.get(variante, 0) + detalle.cantidad
        motivo = MOTIVO_PROVEEDOR.get(devolucion.motivo, DevolucionProveedor.Motivo.OTRO)
        for proveedor, cantidades in al_proveedor.items():
            registrar_devolucion_proveedor(
                proveedor, cantidades, motivo, DevolucionProveedor.Resolucion.REPOSICION, usuario=usuario,
                origen=DevolucionProveedor.Origen.CLIENTE, devolucion=devolucion,
                descripcion=f'Productos de la devolución #{devolucion.pk} (venta {devolucion.venta.numero_factura}).',
            )

    if campos:
        devolucion.save(update_fields=campos)
    return devolucion


# Motivo de la devolución del cliente -> motivo con el que se le devuelve al proveedor
MOTIVO_PROVEEDOR = {
    Devolucion.Motivo.DEFECTO: DevolucionProveedor.Motivo.DEFECTO,
    Devolucion.Motivo.DANADO: DevolucionProveedor.Motivo.DANADO,
    Devolucion.Motivo.EQUIVOCADO: DevolucionProveedor.Motivo.ERROR,
}


@transaction.atomic
def registrar_devolucion_proveedor(proveedor, cantidades, motivo, resolucion, usuario=None,
                                   origen=DevolucionProveedor.Origen.INVENTARIO, devolucion=None,
                                   descripcion=None, factura_proveedor=None):
    """Crea una devolución a proveedor Pendiente. cantidades: {variante: cantidad}.

    Si sale del inventario, el stock se descuenta en el momento (los productos se apartan
    para el proveedor). Si viene de un cliente, esos productos nunca volvieron al stock.
    """
    dp = DevolucionProveedor.objects.create(
        proveedor=proveedor, devolucion=devolucion, usuario=usuario, origen=origen, motivo=motivo,
        resolucion=resolucion, descripcion=descripcion or None, factura_proveedor=factura_proveedor or None,
    )
    for item, cantidad in cantidades.items():
        variante = variante_de(item)
        producto = variante.producto
        DetalleDevolucionProveedor.objects.create(devolucion_proveedor=dp, producto=producto, variante=variante,
                                                  cantidad=cantidad, costo_unitario=producto.precio_compra)
        if origen == DevolucionProveedor.Origen.INVENTARIO:
            registrar_movimiento(variante, MovimientoInventario.Tipo.SALIDA, -cantidad, usuario=usuario,
                                 motivo=f'Devolución al proveedor {proveedor} (#{dp.pk})',
                                 tipo_referencia='DevProveedor', referencia_id=dp.pk)
    return dp


@transaction.atomic
def resolver_devolucion_proveedor(dp, estado_anterior, activa_antes, usuario=None):
    """Se llama después de guardar una devolución a proveedor (estado o vigencia nuevos).

    - Completada con Reposición: las unidades que manda el proveedor entran al stock.
    - Completada con nota de crédito o reembolso: el stock no cambia; se guarda el monto.
    - Rechazada: el proveedor no la aceptó; los productos quedan dados de baja (pérdida).
    - Anular (Activo = 0) solo mientras está Pendiente: lo que salió del inventario regresa.
    Una vez Completada o Rechazada ya no cambia de estado.
    """
    cerrados = (DevolucionProveedor.Estado.COMPLETADA, DevolucionProveedor.Estado.RECHAZADA)
    cambio_estado = dp.estado != estado_anterior
    cambio_vigencia = dp.activo != activa_antes

    if cambio_estado and estado_anterior in cerrados:
        raise ErrorDeNegocio('Esta devolución ya está cerrada y no puede cambiar de estado.')
    if cambio_vigencia and (estado_anterior != DevolucionProveedor.Estado.PENDIENTE or cambio_estado):
        raise ErrorDeNegocio('Solo se puede anular o reactivar una devolución a proveedor mientras está Pendiente.')
    if cambio_estado and not dp.activo:
        raise ErrorDeNegocio('La devolución está anulada: reactívala antes de cambiar su estado.')

    detalles = list(dp.detalles.select_related('producto', 'variante'))
    if cambio_vigencia and dp.origen == DevolucionProveedor.Origen.INVENTARIO:
        signo = -1 if dp.activo else 1        # anular devuelve al stock; reactivar vuelve a sacar
        accion = 'Reactivación' if dp.activo else 'Anulación'
        for d in detalles:
            registrar_movimiento(variante_de(d), MovimientoInventario.Tipo.AJUSTE, signo * d.cantidad, usuario=usuario,
                                 motivo=f'{accion} de la devolución al proveedor #{dp.pk}',
                                 tipo_referencia='DevProveedor', referencia_id=dp.pk)

    if cambio_estado and dp.estado in cerrados:
        dp.fecha_resolucion = timezone.now()
        dp.usuario = usuario or dp.usuario
        dp.save(update_fields=['fecha_resolucion', 'usuario'])
        if dp.estado == DevolucionProveedor.Estado.COMPLETADA and dp.resolucion == DevolucionProveedor.Resolucion.REPOSICION:
            for d in detalles:
                registrar_movimiento(variante_de(d), MovimientoInventario.Tipo.ENTRADA, d.cantidad, usuario=usuario,
                                     motivo=f'Reposición del proveedor {dp.proveedor} (devolución #{dp.pk})',
                                     tipo_referencia='DevProveedor', referencia_id=dp.pk)
    return dp


def siguiente_factura():
    """Número de factura siguiente: V-000001, V-000002..."""
    ultimo = Venta.objects.order_by('-id').values_list('id', flat=True).first() or 0
    numero = ultimo + 1
    while Venta.objects.filter(numero_factura=f'V-{numero:06d}').exists():
        numero += 1
    return f'V-{numero:06d}'


@transaction.atomic
def registrar_venta(cantidades, metodo_pago, cliente=None, usuario=None, estado=Venta.Estado.ENTREGADO,
                    descuento=Decimal('0'), notas=None, canal=Venta.Canal.TIENDA):
    """Registra una venta de mostrador.

    cantidades: {variante: cantidad} (un Producto vale si tiene un solo tono). Usa el precio actual
    de cada producto, descuenta el stock del tono (MovimientoInventario de Salida) y suma puntos al cliente.
    """
    cantidades = {variante_de(item): cantidad for item, cantidad in cantidades.items()}
    subtotal = sum(v.producto.precio_venta * cantidad for v, cantidad in cantidades.items())
    if descuento > subtotal:
        raise ErrorDeNegocio('El descuento no puede ser mayor que el subtotal.')
    puntos = int((subtotal - descuento) * PUNTOS_POR_CORDOBA) if cliente else 0

    venta = Venta.objects.create(
        numero_factura=siguiente_factura(), canal=canal, cliente=cliente, usuario=usuario,
        metodo_pago=metodo_pago, subtotal=subtotal, descuento=descuento, estado=estado,
        puntos_ganados=puntos, notas=notas or None,
    )
    for variante, cantidad in cantidades.items():
        DetalleVenta.objects.create(venta=venta, producto=variante.producto, variante=variante, cantidad=cantidad,
                                    precio_unitario=variante.producto.precio_venta)
        registrar_movimiento(variante, MovimientoInventario.Tipo.SALIDA, -cantidad, usuario=usuario,
                             motivo=f'Venta {venta.numero_factura}', tipo_referencia='Venta', referencia_id=venta.pk)
    if cliente and puntos:
        ajustar_puntos(cliente, puntos, MovimientoPuntos.Tipo.GANADOS, usuario=usuario, venta=venta,
                       descripcion=f'Compra {venta.numero_factura}')
    return venta


@transaction.atomic
def registrar_devolucion(venta, elegidas, motivo, tipo_resolucion, monto_reembolso, descripcion=None):
    """Crea una devolución Pendiente. elegidas: [(detalle_venta, cantidad, destino)].

    destino es un valor de DetalleDevolucion.Destino (Inventario, Baja o Proveedor).

    El stock no se toca hasta que la devolución se marque como Completada.
    """
    devolucion = Devolucion.objects.create(
        venta=venta, motivo=motivo, tipo_resolucion=tipo_resolucion, monto_reembolso=monto_reembolso,
        descripcion=descripcion or None,
    )
    for detalle, cantidad, destino in elegidas:
        DetalleDevolucion.objects.create(devolucion=devolucion, detalle_venta=detalle, cantidad=cantidad, destino=destino,
                                         regresa_a_inventario=destino == DetalleDevolucion.Destino.INVENTARIO)
    return devolucion


@transaction.atomic
def unir_como_tono(destino, origen, nombre_destino=None, nombre_origen=None, usuario=None):
    """Une un producto registrado aparte (ej. otro tono del mismo labial) como tono(s) de destino.

    - Si alguno de los dos no tiene tonos, su stock pasa a ser un tono con el nombre indicado,
      con el SKU y la foto principal de ese producto.
    - Los tonos de origen pasan a destino con su stock; el historial (movimientos, ventas, compras,
      devoluciones a proveedor) y las reseñas se mueven con ellos.
    - origen queda deshabilitado con stock 0. No se borra nada.
    Devuelve la lista de tonos que se agregaron a destino.
    """
    if destino.pk == origen.pk:
        raise ErrorDeNegocio('Elige un producto distinto.')
    destino = Producto.objects.select_for_update().get(pk=destino.pk)
    origen = Producto.objects.select_for_update().get(pk=origen.pk)
    for producto in (destino, origen):
        if not producto.variantes.exists():
            variante_unica(producto)

    for producto, nombre in ((destino, nombre_destino), (origen, nombre_origen)):
        unica = producto.variantes.filter(nombre=VarianteProducto.UNICA).first()
        if unica is None:
            continue
        nombre = (nombre or '').strip()
        if not nombre:
            raise ErrorDeNegocio(f'Escribe el nombre del tono de "{producto.nombre}" (SKU {producto.sku}).')
        if nombre.lower() == VarianteProducto.UNICA.lower():
            raise ErrorDeNegocio(f'"{VarianteProducto.UNICA}" está reservado: usa el nombre del tono.')
        foto = producto.imagenes.filter(activo=True, es_principal=True).first()
        sku = unica.sku or (producto.sku if not VarianteProducto.objects.filter(sku__iexact=producto.sku).exists()
                            else None)
        VarianteProducto.objects.filter(pk=unica.pk).update(
            nombre=nombre, sku=sku, imagen=unica.imagen.name if unica.imagen else (foto.ruta.name if foto else None))

    nombres = {n.lower() for n in destino.variantes.values_list('nombre', flat=True)}
    nuevos = list(origen.variantes.order_by('orden', 'id'))
    repetidos = [v.nombre for v in nuevos if v.nombre.lower() in nombres]
    if repetidos:
        raise ErrorDeNegocio(f'{destino.nombre} ya tiene un tono llamado "{repetidos[0]}". Usa otro nombre.')

    orden = (destino.variantes.order_by('-orden').values_list('orden', flat=True).first() or 0) + 1
    for i, variante in enumerate(nuevos):
        VarianteProducto.objects.filter(pk=variante.pk).update(producto_id=destino.pk, orden=orden + i)
    for modelo in (MovimientoInventario, DetalleVenta, DetalleCompra, DetalleDevolucionProveedor):
        modelo.objects.filter(producto_id=origen.pk).update(producto_id=destino.pk)
    con_resena = Resena.objects.filter(producto_id=destino.pk).values('cliente_id')
    Resena.objects.filter(producto_id=origen.pk).exclude(cliente_id__in=con_resena).update(producto_id=destino.pk)

    sincronizar_producto(destino.pk)
    sincronizar_producto(origen.pk)
    Producto.objects.filter(pk=origen.pk).update(activo=False)
    return VarianteProducto.objects.filter(pk__in=[v.pk for v in nuevos])

