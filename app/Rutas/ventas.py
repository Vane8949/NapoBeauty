from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from app.formularios import LineasVenta, VentaForm, VentaNuevaForm
from app.models import Cliente, Venta
from app.servicios import ErrorDeNegocio, cambiar_estado_venta, registrar_venta

from .comun import guardado, mostrar_formulario, paginar, requiere_permiso, tiene_permiso, usuario_actual


@requiere_permiso('ventas.ver')
def panel_ventas(request):
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')
    canal = request.GET.get('canal', '')

    ventas = Venta.objects.select_related('cliente', 'metodo_pago')
    if q:
        ventas = ventas.filter(Q(numero_factura__icontains=q) | Q(cliente__nombre__icontains=q) |
                               Q(cliente__apellido__icontains=q) | Q(cliente__correo__icontains=q))
    if estado == 'anuladas':
        ventas = ventas.filter(activo=False)
    elif estado in Venta.Estado.values:
        ventas = ventas.filter(estado=estado, activo=True)
    if canal in Venta.Canal.values:
        ventas = ventas.filter(canal=canal)
    pagina, filtros = paginar(request, ventas.order_by('-fecha', '-id'))

    hoy = timezone.now().date()
    inicio_mes = hoy.replace(day=1)
    vigentes = Venta.objects.filter(activo=True)
    del_mes = vigentes.filter(fecha__date__gte=inicio_mes).aggregate(
        cantidad=Count('id'), monto=Sum('total'), promedio=Avg('total'))
    contexto = {
        'pagina': pagina, 'filtros': filtros, 'q': q, 'estado': estado, 'canal': canal,
        'busqueda': bool(q or estado or canal),
        'estados': Venta.Estado.choices, 'canales': Venta.Canal.choices,
        'kpi': {
            'hoy': vigentes.filter(fecha__date=hoy).aggregate(t=Sum('total'))['t'] or 0,
            'pedidos_mes': del_mes['cantidad'],
            'monto_mes': del_mes['monto'] or 0,
            'ticket': del_mes['promedio'] or 0,
        },
        'puede_editar': tiene_permiso(request, 'ventas.editar'),
        'puede_crear': tiene_permiso(request, 'ventas.crear'),
    }
    return render(request, 'ventas/index.html', contexto)


@requiere_permiso('ventas.ver')
def detalle_venta(request, pk):
    venta = get_object_or_404(
        Venta.objects.select_related('cliente', 'usuario', 'metodo_pago', 'direccion_cliente'), pk=pk)
    return render(request, 'ventas/detalle.html', {
        'venta': venta,
        'detalles': venta.detalles.select_related('producto__marca', 'variante'),
        'devoluciones': venta.devoluciones.all(),
        'puede_editar': tiene_permiso(request, 'ventas.editar'),
        'puede_devolver': venta.activo and tiene_permiso(request, 'devoluciones.crear'),
    })


@requiere_permiso('ventas.crear')
def crear_venta(request):
    """Registrar venta de mostrador: varias líneas de productos, total en pantalla.

    Toda venta lleva cliente: uno registrado o uno nuevo, que se registra junto con la venta.
    Al guardar se abre el recibo para imprimirlo.
    """
    form = VentaNuevaForm(request.POST or None)
    lineas = LineasVenta(request.POST or None, prefix='lineas')

    if request.method == 'POST' and all([form.is_valid(), lineas.is_valid()]):   # valida ambos para mostrar todos los errores
        datos = form.cleaned_data
        try:
            with transaction.atomic():     # si la venta falla, el cliente nuevo tampoco queda registrado
                cliente = datos['cliente']
                nuevo = datos.get('datos_cliente_nuevo')
                if nuevo:
                    cliente = Cliente.objects.create(**nuevo)
                venta = registrar_venta(
                    lineas.cantidades, datos['metodo_pago'], cliente=cliente, usuario=usuario_actual(request),
                    estado=datos['estado'], descuento=datos['descuento'], notas=datos['notas'],
                )
        except ErrorDeNegocio as error:
            form.add_error(None, str(error))
        else:
            texto = f'Venta {venta.numero_factura} registrada por C$ {venta.subtotal - venta.descuento:,.2f}.'
            if nuevo:
                texto += f' Cliente {cliente} registrado.'
            return guardado(request, reverse('venta_recibo', args=[venta.pk]) + '?nueva=1', texto, ir=True)

    return mostrar_formulario(request, {
        'form': form, 'lineas': lineas, 'seccion_extra': 'ventas/lineas_venta.html',
        'titulo': 'Registrar venta', 'icono': 'fa-cart-plus', 'ancho': 'xl', 'texto_boton': 'Registrar venta',
        'volver_url': reverse('ventas'),
    })


@requiere_permiso('ventas.ver')
def recibo_venta(request, pk):
    """Recibo de la compra en formato ticket de 80 mm, listo para imprimir o guardar como PDF."""
    venta = get_object_or_404(Venta.objects.select_related('cliente', 'usuario', 'metodo_pago'), pk=pk)
    return render(request, 'ventas/recibo.html', {
        'venta': venta,
        'detalles': venta.detalles.select_related('producto__marca', 'variante').order_by('id'),
        'tienda': getattr(settings, 'NAPO_TIENDA', {'nombre': 'Napo Beauty'}),
        'nueva': request.GET.get('nueva') == '1',
        'unidades': sum(d.cantidad for d in venta.detalles.all()),
    })


@requiere_permiso('ventas.editar')
def editar_venta(request, pk):
    venta = get_object_or_404(Venta.objects.select_related('cliente', 'metodo_pago'), pk=pk)
    estaba_activa = venta.activo
    form = VentaForm(request.POST or None, instance=venta)
    if not tiene_permiso(request, 'ventas.habilitar'):
        form.fields['activo'].disabled = True

    if request.method == 'POST' and form.is_valid():
        activa = form.cleaned_data['activo']
        try:
            with transaction.atomic():
                venta = form.save(commit=False)
                venta.save(update_fields=['estado', 'metodo_pago', 'notas'])   # la vigencia la cambia el servicio
                if activa != estaba_activa:
                    cambiar_estado_venta(venta, activa, usuario=usuario_actual(request))
        except ErrorDeNegocio as error:
            form.add_error(None, str(error))
        else:
            url = reverse('venta_detalle', args=[venta.pk])
            if activa != estaba_activa:
                texto = ('Venta reactivada: los productos se volvieron a descontar del inventario.' if activa else
                         'Venta anulada: los productos regresaron al inventario.')
                return guardado(request, url, texto, messages.WARNING)
            return guardado(request, url, f'Se guardaron los cambios de la venta {venta.numero_factura}.')

    cliente = str(venta.cliente) if venta.cliente_id else 'Cliente de mostrador'
    return mostrar_formulario(request, {
        'form': form, 'titulo': f'Editar venta {venta.numero_factura}', 'icono': 'fa-pen-to-square',
        'subtitulo': 'Los productos y montos no se modifican; si hubo un error, anula la venta.',
        'volver_url': reverse('venta_detalle', args=[venta.pk]),
        'resumen': [('Cliente', cliente), ('Fecha', venta.fecha.strftime('%d/%m/%Y')),
                    ('Canal', venta.get_canal_display()), ('Total', f'C$ {venta.total:,.2f}')],
    })
