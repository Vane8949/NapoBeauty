from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Max, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from app.formularios import AjusteInventarioForm
from app.models import MovimientoInventario, Producto
from app.servicios import ErrorDeNegocio, registrar_movimiento

from .comun import guardado, mostrar_formulario, paginar, requiere_permiso, tiene_permiso, usuario_actual


@requiere_permiso('inventario.ver')
def panel_inventario(request):
    q = request.GET.get('q', '').strip()
    stock = request.GET.get('stock', '')

    productos = (Producto.objects.filter(activo=True)
                 .select_related('categoria', 'marca')
                 .annotate(ultimo_movimiento=Max('movimientos__fecha')))
    if q:
        productos = productos.filter(Q(nombre__icontains=q) | Q(sku__icontains=q) | Q(marca__nombre__icontains=q))
    if stock == 'bajo':
        productos = productos.filter(stock_actual__gt=0, stock_actual__lte=F('stock_minimo'))
    elif stock == 'agotado':
        productos = productos.filter(stock_actual=0)
    pagina, filtros = paginar(request, productos.order_by('nombre'))

    activos = Producto.objects.filter(activo=True)
    valor = activos.aggregate(
        unidades=Sum('stock_actual'),
        valor=Sum(ExpressionWrapper(F('stock_actual') * F('precio_compra'),
                                    output_field=DecimalField(max_digits=18, decimal_places=2))),
    )
    contexto = {
        'pagina': pagina, 'filtros': filtros, 'q': q, 'stock': stock, 'busqueda': bool(q or stock),
        'kpi': {
            'unidades': valor['unidades'] or 0,
            'valor': valor['valor'] or 0,
            'bajo_stock': activos.filter(stock_actual__gt=0, stock_actual__lte=F('stock_minimo')).count(),
            'agotados': activos.filter(stock_actual=0).count(),
        },
        'puede_ajustar': tiene_permiso(request, 'inventario.crear'),
    }
    return render(request, 'inventario/index.html', contexto)


@requiere_permiso('inventario.ver')
def detalle_inventario(request, pk):
    producto = get_object_or_404(Producto.objects.select_related('categoria', 'marca'), pk=pk)
    tipo = request.GET.get('tipo', '')
    movimientos = producto.movimientos.select_related('usuario')
    if tipo in MovimientoInventario.Tipo.values:
        movimientos = movimientos.filter(tipo=tipo)
    pagina, filtros = paginar(request, movimientos.order_by('-fecha', '-id'), por_pagina=20)

    totales = producto.movimientos.aggregate(
        entradas=Sum('cantidad', filter=Q(cantidad__gt=0)), salidas=Sum('cantidad', filter=Q(cantidad__lt=0)))
    return render(request, 'inventario/detalle.html', {
        'producto': producto, 'pagina': pagina, 'filtros': filtros, 'tipo': tipo,
        'tipos': MovimientoInventario.Tipo.choices,
        'entradas': totales['entradas'] or 0, 'salidas': -(totales['salidas'] or 0),
        'puede_ajustar': tiene_permiso(request, 'inventario.crear'),
    })


@requiere_permiso('inventario.crear')
def ajustar_inventario(request, pk=None):
    """Ajuste de stock de un producto (lápiz de la fila) o eligiendo el producto (botón "Ajustar Stock")."""
    producto = get_object_or_404(Producto.objects.select_related('marca'), pk=pk) if pk else None
    form = AjusteInventarioForm(request.POST or None, producto=producto)

    if request.method == 'POST' and form.is_valid():
        datos, producto = form.cleaned_data, form.producto
        try:
            with transaction.atomic():
                if datos['cambio']:
                    registrar_movimiento(producto, datos['tipo'], datos['cambio'],
                                         usuario=usuario_actual(request), motivo=datos['motivo'])
                if datos['stock_minimo'] != producto.stock_minimo:
                    Producto.objects.filter(pk=producto.pk).update(stock_minimo=datos['stock_minimo'])
        except ErrorDeNegocio as error:
            form.add_error(None, str(error))
        else:
            producto.refresh_from_db()
            return guardado(request, reverse('inventario_detalle', args=[producto.pk]),
                            f'Inventario actualizado: {producto.nombre} tiene ahora {producto.stock_actual} unidades.')

    contexto = {'form': form, 'titulo': 'Ajuste de stock', 'icono': 'fa-boxes-stacked',
                'texto_boton': 'Confirmar ajuste', 'volver_url': reverse('inventario')}
    if producto:
        contexto.update({
            'subtitulo': f'{producto.sku} · {producto.nombre}',
            'volver_url': reverse('inventario_detalle', args=[producto.pk]),
            'resumen': [('Stock actual', producto.stock_actual), ('Stock mínimo', producto.stock_minimo),
                        ('Marca', producto.marca.nombre), ('Estado', 'Activo' if producto.activo else 'Inactivo')],
        })
    return mostrar_formulario(request, contexto)


@requiere_permiso('inventario.ver')
def movimientos_inventario(request):
    """Historial de movimientos de todos los productos (botón "Movimientos")."""
    tipo = request.GET.get('tipo', '')
    movimientos = MovimientoInventario.objects.select_related('producto', 'usuario')
    if tipo in MovimientoInventario.Tipo.values:
        movimientos = movimientos.filter(tipo=tipo)
    pagina, filtros = paginar(request, movimientos.order_by('-fecha', '-id'), por_pagina=25)
    return render(request, 'inventario/movimientos.html', {
        'pagina': pagina, 'filtros': filtros, 'tipo': tipo, 'tipos': MovimientoInventario.Tipo.choices,
    })
