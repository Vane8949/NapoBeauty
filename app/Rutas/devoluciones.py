from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from app.formularios import DevolucionForm, DevolucionNuevaForm
from app.models import Devolucion, Venta
from app.servicios import ErrorDeNegocio, registrar_devolucion, resolver_devolucion

from .comun import guardado, mostrar_formulario, paginar, requiere_permiso, tiene_permiso, usuario_actual


@requiere_permiso('devoluciones.ver')
def panel_devoluciones(request):
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')

    devoluciones = Devolucion.objects.select_related('venta__cliente')
    if q:
        filtro = (Q(venta__numero_factura__icontains=q) | Q(venta__cliente__nombre__icontains=q) |
                  Q(venta__cliente__apellido__icontains=q))
        if q.lstrip('#').isdigit():
            filtro |= Q(pk=int(q.lstrip('#')))
        devoluciones = devoluciones.filter(filtro)
    if estado == 'anuladas':
        devoluciones = devoluciones.filter(activo=False)
    elif estado in Devolucion.Estado.values:
        devoluciones = devoluciones.filter(estado=estado, activo=True)
    pagina, filtros = paginar(request, devoluciones.order_by('-fecha_solicitud', '-id'))

    vigentes = Devolucion.objects.filter(activo=True)
    motivo = vigentes.values('motivo').annotate(n=Count('id')).order_by('-n').first()
    contexto = {
        'pagina': pagina, 'filtros': filtros, 'q': q, 'estado': estado, 'busqueda': bool(q or estado),
        'estados': Devolucion.Estado.choices,
        'kpi': {
            'total': vigentes.count(),
            'pendientes': vigentes.filter(estado=Devolucion.Estado.PENDIENTE).count(),
            'reembolsado': vigentes.filter(
                tipo_resolucion=Devolucion.TipoResolucion.REEMBOLSO,
                estado__in=[Devolucion.Estado.APROBADA, Devolucion.Estado.COMPLETADA],
            ).aggregate(t=Sum('monto_reembolso'))['t'] or 0,
            'motivo': motivo['motivo'] if motivo else None,
        },
        'puede_editar': tiene_permiso(request, 'devoluciones.editar'),
        'puede_crear': tiene_permiso(request, 'devoluciones.crear'),
        'pestana': 'clientes',
    }
    return render(request, 'devoluciones/index.html', contexto)


@requiere_permiso('devoluciones.ver')
def detalle_devolucion(request, pk):
    devolucion = get_object_or_404(
        Devolucion.objects.select_related('venta__cliente', 'venta__metodo_pago', 'usuario'), pk=pk)
    return render(request, 'devoluciones/detalle.html', {
        'devolucion': devolucion,
        'detalles': devolucion.detalles.select_related('detalle_venta__producto__marca'),
        'al_proveedor': devolucion.devoluciones_proveedor.select_related('proveedor'),
        'puede_editar': tiene_permiso(request, 'devoluciones.editar'),
    })


@requiere_permiso('devoluciones.crear')
def crear_devolucion(request):
    """Registrar devolución: se elige la venta y luego cuántas unidades de cada producto se devuelven."""
    venta_id = request.POST.get('venta') or request.GET.get('venta')
    venta = (Venta.objects.filter(pk=venta_id, activo=True).select_related('cliente').first()
             if venta_id and str(venta_id).isdigit() else None)
    # Si solo cambió la venta elegida (GET), el formulario se dibuja de nuevo con sus productos
    datos = request.POST if request.method == 'POST' else None
    form = DevolucionNuevaForm(datos, venta=venta)

    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        devolucion = registrar_devolucion(d['venta'], d['elegidas'], d['motivo'], d['tipo_resolucion'],
                                          d['monto_reembolso'], d['descripcion'])
        return guardado(request, reverse('devolucion_detalle', args=[devolucion.pk]),
                        f'Devolución #{devolucion.pk} registrada como Pendiente. El stock se ajusta al completarla.')

    form.fields['venta'].widget.attrs['data-recargar'] = reverse('devolucion_crear')
    return mostrar_formulario(request, {
        'form': form, 'titulo': 'Registrar devolución', 'icono': 'fa-arrow-rotate-left', 'ancho': 'lg',
        'texto_boton': 'Registrar devolución', 'seccion_extra': 'devoluciones/lineas_devolucion.html',
        'volver_url': reverse('devoluciones'), 'venta_elegida': venta,
    })


@requiere_permiso('devoluciones.editar')
def editar_devolucion(request, pk):
    devolucion = get_object_or_404(Devolucion.objects.select_related('venta__cliente'), pk=pk)
    estado_anterior = devolucion.estado
    form = DevolucionForm(request.POST or None, instance=devolucion)
    if not tiene_permiso(request, 'devoluciones.habilitar'):
        form.fields['activo'].disabled = True

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                devolucion = form.save()
                resolver_devolucion(devolucion, estado_anterior, usuario=usuario_actual(request))
        except ErrorDeNegocio as error:
            form.add_error(None, str(error))
        else:
            if devolucion.estado == Devolucion.Estado.COMPLETADA and estado_anterior != devolucion.estado:
                texto = f'Devolución #{devolucion.pk} completada. Los productos que regresan al stock se sumaron al inventario.'
                enviadas = devolucion.devoluciones_proveedor.count()
                if enviadas:
                    texto += (f' Se creó {enviadas} devolución{"es" if enviadas > 1 else ""} a proveedor '
                              f'con los productos que van al proveedor.')
            else:
                texto = f'Se guardaron los cambios de la devolución #{devolucion.pk}.'
            return guardado(request, reverse('devolucion_detalle', args=[devolucion.pk]), texto)

    venta = devolucion.venta
    return mostrar_formulario(request, {
        'form': form, 'titulo': f'Editar devolución #{devolucion.pk}', 'icono': 'fa-pen-to-square',
        'subtitulo': f'Venta {venta.numero_factura}',
        'volver_url': reverse('devolucion_detalle', args=[devolucion.pk]),
        'resumen': [('Cliente', str(venta.cliente) if venta.cliente_id else 'Mostrador'),
                    ('Venta', venta.numero_factura), ('Total venta', f'C$ {venta.total:,.2f}'),
                    ('Solicitada', devolucion.fecha_solicitud.strftime('%d/%m/%Y'))],
    })
