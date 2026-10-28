"""Devoluciones a proveedores: productos que la tienda le regresa a un proveedor."""
from django.db import transaction
from django.db.models import F, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from app.formularios import DevolucionProveedorForm, DevolucionProveedorNuevaForm, LineasDevProveedor
from app.models import DetalleDevolucionProveedor, DevolucionProveedor, Proveedor
from app.servicios import ErrorDeNegocio, registrar_devolucion_proveedor, resolver_devolucion_proveedor

from .comun import guardado, mostrar_formulario, paginar, requiere_permiso, tiene_permiso, usuario_actual


@requiere_permiso('devoluciones.ver')
def panel_devoluciones_proveedor(request):
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')
    origen = request.GET.get('origen', '')

    devoluciones = DevolucionProveedor.objects.select_related('proveedor', 'devolucion').annotate(
        unidades=Sum('detalles__cantidad'), costo=Sum('detalles__subtotal'))
    if q:
        filtro = Q(proveedor__nombre_empresa__icontains=q) | Q(factura_proveedor__icontains=q)
        if q.lstrip('#').isdigit():
            filtro |= Q(pk=int(q.lstrip('#')))
        devoluciones = devoluciones.filter(filtro)
    if estado == 'anuladas':
        devoluciones = devoluciones.filter(activo=False)
    elif estado in DevolucionProveedor.Estado.values:
        devoluciones = devoluciones.filter(estado=estado, activo=True)
    if origen in DevolucionProveedor.Origen.values:
        devoluciones = devoluciones.filter(origen=origen)
    pagina, filtros = paginar(request, devoluciones.order_by('-fecha', '-id'))

    vigentes = DevolucionProveedor.objects.filter(activo=True)
    detalles = DetalleDevolucionProveedor.objects.filter(devolucion_proveedor__activo=True)
    contexto = {
        'pagina': pagina, 'filtros': filtros, 'q': q, 'estado': estado, 'origen': origen,
        'busqueda': bool(q or estado or origen),
        'estados': DevolucionProveedor.Estado.choices, 'origenes': DevolucionProveedor.Origen.choices,
        'kpi': {
            'total': vigentes.count(),
            'abiertas': vigentes.filter(estado__in=[DevolucionProveedor.Estado.PENDIENTE,
                                                    DevolucionProveedor.Estado.ENVIADA]).count(),
            'unidades': detalles.aggregate(t=Sum('cantidad'))['t'] or 0,
            'acreditado': vigentes.filter(estado=DevolucionProveedor.Estado.COMPLETADA).aggregate(
                t=Sum('monto_credito'))['t'] or 0,
        },
        'puede_editar': tiene_permiso(request, 'devoluciones.editar'),
        'puede_crear': tiene_permiso(request, 'devoluciones.crear'),
        'pestana': 'proveedores',
    }
    return render(request, 'devoluciones/proveedores.html', contexto)


@requiere_permiso('devoluciones.ver')
def detalle_devolucion_proveedor(request, pk):
    dp = get_object_or_404(
        DevolucionProveedor.objects.select_related('proveedor', 'devolucion__venta', 'usuario'), pk=pk)
    detalles = dp.detalles.select_related('producto__marca', 'variante')
    return render(request, 'devoluciones/detalle_proveedor.html', {
        'dp': dp, 'detalles': detalles,
        'totales': detalles.aggregate(unidades=Sum('cantidad'), costo=Sum('subtotal')),
        'puede_editar': tiene_permiso(request, 'devoluciones.editar'),
    })


@requiere_permiso('devoluciones.crear')
def crear_devolucion_proveedor(request):
    """Elegir el proveedor (recarga el formulario con sus productos primero) y los productos que se devuelven."""
    proveedor_id = request.POST.get('proveedor') or request.GET.get('proveedor')
    proveedor = (Proveedor.objects.filter(pk=proveedor_id, activo=True).first()
                 if proveedor_id and str(proveedor_id).isdigit() else None)
    datos = request.POST if request.method == 'POST' else None
    form = DevolucionProveedorNuevaForm(datos, initial={'proveedor': proveedor.pk} if proveedor else None)
    lineas = LineasDevProveedor(datos, prefix='lineas', form_kwargs={'proveedor': proveedor})

    if request.method == 'POST' and all([form.is_valid(), lineas.is_valid()]):
        d = form.cleaned_data
        try:
            dp = registrar_devolucion_proveedor(
                d['proveedor'], lineas.cantidades, d['motivo'], d['resolucion'], usuario=usuario_actual(request),
                descripcion=d['descripcion'], factura_proveedor=d['factura_proveedor'],
            )
        except ErrorDeNegocio as error:
            form.add_error(None, str(error))
        else:
            unidades = sum(lineas.cantidades.values())
            return guardado(request, reverse('devolucion_proveedor_detalle', args=[dp.pk]),
                            f'Devolución a {dp.proveedor} #{dp.pk} registrada: '
                            + ('1 unidad salió' if unidades == 1 else f'{unidades} unidades salieron')
                            + ' del inventario.')

    form.fields['proveedor'].widget.attrs['data-recargar'] = reverse('devolucion_proveedor_crear')
    return mostrar_formulario(request, {
        'form': form, 'lineas': lineas, 'seccion_extra': 'devoluciones/lineas_proveedor.html',
        'titulo': 'Devolver productos al proveedor', 'icono': 'fa-truck-ramp-box', 'ancho': 'xl',
        'subtitulo': 'Para productos defectuosos, vencidos o de un pedido equivocado que están en el inventario.',
        'texto_boton': 'Registrar devolución', 'volver_url': reverse('devoluciones_proveedor'),
    })


@requiere_permiso('devoluciones.editar')
def editar_devolucion_proveedor(request, pk):
    dp = get_object_or_404(DevolucionProveedor.objects.select_related('proveedor'), pk=pk)
    estado_anterior, activa_antes = dp.estado, dp.activo
    form = DevolucionProveedorForm(request.POST or None, instance=dp)
    if not tiene_permiso(request, 'devoluciones.habilitar'):
        form.fields['activo'].disabled = True

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                dp = form.save()
                resolver_devolucion_proveedor(dp, estado_anterior, activa_antes, usuario=usuario_actual(request))
        except ErrorDeNegocio as error:
            form.add_error(None, str(error))
        else:
            if dp.activo != activa_antes:
                texto = ('Devolución reactivada: los productos volvieron a salir del inventario.' if dp.activo else
                         'Devolución anulada: los productos regresaron al inventario.'
                         if dp.origen == DevolucionProveedor.Origen.INVENTARIO else 'Devolución anulada.')
            elif dp.estado != estado_anterior and dp.estado == DevolucionProveedor.Estado.COMPLETADA:
                texto = (f'Devolución #{dp.pk} completada. Las unidades repuestas se sumaron al stock.'
                         if dp.resolucion == DevolucionProveedor.Resolucion.REPOSICION else
                         f'Devolución #{dp.pk} completada con {dp.get_resolucion_display().lower()} de C$ {dp.monto_credito:,.2f}.')
            elif dp.estado != estado_anterior and dp.estado == DevolucionProveedor.Estado.RECHAZADA:
                texto = f'Devolución #{dp.pk} rechazada por el proveedor: los productos quedan dados de baja.'
            else:
                texto = f'Se guardaron los cambios de la devolución a proveedor #{dp.pk}.'
            return guardado(request, reverse('devolucion_proveedor_detalle', args=[dp.pk]), texto)

    totales = dp.detalles.aggregate(unidades=Sum('cantidad'), costo=Sum(F('cantidad') * F('costo_unitario')))
    return mostrar_formulario(request, {
        'form': form, 'titulo': f'Editar devolución a proveedor #{dp.pk}', 'icono': 'fa-pen-to-square',
        'subtitulo': str(dp.proveedor),
        'volver_url': reverse('devolucion_proveedor_detalle', args=[dp.pk]),
        'resumen': [('Proveedor', str(dp.proveedor)), ('Origen', dp.get_origen_display()),
                    ('Unidades', totales['unidades'] or 0), ('Costo', f'C$ {totales["costo"] or 0:,.2f}')],
    })

