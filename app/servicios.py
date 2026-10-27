"""Reglas del negocio que tocan varias tablas a la vez.

Todo cambio de stock pasa por registrar_movimiento(): actualiza Producto.StockActual
y deja la huella en MovimientoInventario dentro de la misma transacción.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from app.models import (
    Cliente, DetalleDevolucion, DetalleDevolucionProveedor, DetalleVenta, Devolucion, DevolucionProveedor,
    MovimientoInventario, MovimientoPuntos, Producto, Venta,
)

PUNTOS_POR_CORDOBA = Decimal('0.1')     # 1 punto por cada C$ 10 de compra


class ErrorDeNegocio(Exception):
    """Operación no permitida por las reglas de Napo Beauty (el mensaje se muestra al usuario)."""


@transaction.atomic
def registrar_movimiento(producto, tipo, cantidad, usuario=None, motivo=None,
                         tipo_referencia=None, referencia_id=None):
    """Suma (cantidad > 0) o resta (cantidad < 0) stock y guarda el movimiento.

    Bloquea la fila del producto mientras dura la transacción para que dos ajustes
    simultáneos no se pisen.
    """
    if cantidad == 0:
        raise ErrorDeNegocio('La cantidad del movimiento no puede ser cero.')

    producto = Producto.objects.select_for_update().get(pk=producto.pk)
    anterior = producto.stock_actual
    nuevo = anterior + cantidad
    if nuevo < 0:
        raise ErrorDeNegocio(
            f'No hay suficiente stock de {producto.nombre}: hay {anterior} y se intentan sacar {-cantidad}.')

    producto.stock_actual = nuevo
    producto.save(update_fields=['stock_actual'])
    return MovimientoInventario.objects.create(
        producto=producto, usuario=usuario, tipo=tipo, cantidad=cantidad,
        stock_anterior=anterior, stock_nuevo=nuevo, motivo=motivo,
        tipo_referencia=tipo_referencia, referencia_id=referencia_id,
    )


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
    for detalle in venta.detalles.select_related('producto'):
        registrar_movimiento(
            detalle.producto, MovimientoInventario.Tipo.AJUSTE, signo * detalle.cantidad, usuario=usuario,
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
        for detalle in devolucion.detalles.select_related('detalle_venta__producto__proveedor'):
            producto = detalle.detalle_venta.producto
            if detalle.destino == DetalleDevolucion.Destino.INVENTARIO:
                registrar_movimiento(
                    producto, MovimientoInventario.Tipo.DEVOLUCION, detalle.cantidad,
                    usuario=usuario, motivo=f'Devolución #{devolucion.pk}',
                    tipo_referencia='Devolucion', referencia_id=devolucion.pk,
                )
            elif detalle.destino == DetalleDevolucion.Destino.PROVEEDOR:
                if producto.proveedor_id is None:
                    raise ErrorDeNegocio(f'{producto.nombre} no tiene proveedor asignado. Asígnaselo en Productos '
                                         f'para poder devolverlo al proveedor.')
                productos = al_proveedor.setdefault(producto.proveedor, {})
                productos[producto] = productos.get(producto, 0) + detalle.cantidad
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
    """Crea una devolución a proveedor Pendiente. cantidades: {producto: cantidad}.

    Si sale del inventario, el stock se descuenta en el momento (los productos se apartan
    para el proveedor). Si viene de un cliente, esos productos nunca volvieron al stock.
    """
    dp = DevolucionProveedor.objects.create(
        proveedor=proveedor, devolucion=devolucion, usuario=usuario, origen=origen, motivo=motivo,
        resolucion=resolucion, descripcion=descripcion or None, factura_proveedor=factura_proveedor or None,
    )
    for producto, cantidad in cantidades.items():
        DetalleDevolucionProveedor.objects.create(devolucion_proveedor=dp, producto=producto, cantidad=cantidad,
                                                  costo_unitario=producto.precio_compra)
        if origen == DevolucionProveedor.Origen.INVENTARIO:
            registrar_movimiento(producto, MovimientoInventario.Tipo.SALIDA, -cantidad, usuario=usuario,
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

    detalles = list(dp.detalles.select_related('producto'))
    if cambio_vigencia and dp.origen == DevolucionProveedor.Origen.INVENTARIO:
        signo = -1 if dp.activo else 1        # anular devuelve al stock; reactivar vuelve a sacar
        accion = 'Reactivación' if dp.activo else 'Anulación'
        for d in detalles:
            registrar_movimiento(d.producto, MovimientoInventario.Tipo.AJUSTE, signo * d.cantidad, usuario=usuario,
                                 motivo=f'{accion} de la devolución al proveedor #{dp.pk}',
                                 tipo_referencia='DevProveedor', referencia_id=dp.pk)

    if cambio_estado and dp.estado in cerrados:
        dp.fecha_resolucion = timezone.now()
        dp.usuario = usuario or dp.usuario
        dp.save(update_fields=['fecha_resolucion', 'usuario'])
        if dp.estado == DevolucionProveedor.Estado.COMPLETADA and dp.resolucion == DevolucionProveedor.Resolucion.REPOSICION:
            for d in detalles:
                registrar_movimiento(d.producto, MovimientoInventario.Tipo.ENTRADA, d.cantidad, usuario=usuario,
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

    cantidades: {producto: cantidad}. Usa el precio actual de cada producto, descuenta el
    stock (MovimientoInventario de Salida) y suma puntos al cliente.
    """
    subtotal = sum(producto.precio_venta * cantidad for producto, cantidad in cantidades.items())
    if descuento > subtotal:
        raise ErrorDeNegocio('El descuento no puede ser mayor que el subtotal.')
    puntos = int((subtotal - descuento) * PUNTOS_POR_CORDOBA) if cliente else 0

    venta = Venta.objects.create(
        numero_factura=siguiente_factura(), canal=canal, cliente=cliente, usuario=usuario,
        metodo_pago=metodo_pago, subtotal=subtotal, descuento=descuento, estado=estado,
        puntos_ganados=puntos, notas=notas or None,
    )
    for producto, cantidad in cantidades.items():
        DetalleVenta.objects.create(venta=venta, producto=producto, cantidad=cantidad,
                                    precio_unitario=producto.precio_venta)
        registrar_movimiento(producto, MovimientoInventario.Tipo.SALIDA, -cantidad, usuario=usuario,
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
