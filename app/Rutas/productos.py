from django.db.models import Avg, Count, F, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from app.formularios import ProductoForm
from app.models import Categoria, MovimientoInventario, Producto, ProductoImagen
from app.servicios import ErrorDeNegocio, registrar_movimiento

from .comun import (filtrar_estado, guardado, mostrar_formulario, paginar, requiere_permiso, tiene_permiso,
                    usuario_actual, validar_en_transaccion)


@requiere_permiso('productos.ver')
def panel_productos(request):
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')
    categoria = request.GET.get('categoria', '')

    productos = Producto.objects.select_related('categoria__categoria_padre', 'marca')
    if q:
        productos = productos.filter(Q(nombre__icontains=q) | Q(sku__icontains=q) | Q(marca__nombre__icontains=q))
    if categoria.isdigit():
        productos = productos.filter(Q(categoria_id=categoria) | Q(categoria__categoria_padre_id=categoria))
    productos = filtrar_estado(productos, estado).order_by('nombre')
    pagina, filtros = paginar(request, productos)

    activos = Producto.objects.filter(activo=True)
    contexto = {
        'pagina': pagina, 'filtros': filtros, 'q': q, 'estado': estado, 'categoria': categoria,
        'busqueda': bool(q or estado or categoria),
        'categorias': Categoria.objects.filter(categoria_padre__isnull=True, activo=True),
        'kpi': {
            'total': Producto.objects.count(),
            'categorias': Categoria.objects.filter(activo=True).count(),
            'bajo_stock': activos.filter(stock_actual__lte=F('stock_minimo')).count(),
            'inactivos': Producto.objects.filter(activo=False).count(),
        },
        'puede_editar': tiene_permiso(request, 'productos.editar'),
        'puede_crear': tiene_permiso(request, 'productos.crear'),
    }
    return render(request, 'productos/index.html', contexto)


@requiere_permiso('productos.ver')
def detalle_producto(request, pk):
    producto = get_object_or_404(
        Producto.objects.select_related('categoria__categoria_padre', 'marca', 'proveedor'), pk=pk)
    vendidos = producto.detalles_venta.filter(venta__activo=True).aggregate(
        unidades=Sum('cantidad'), ingresos=Sum('subtotal'))
    resenas = producto.resenas.filter(activo=True).aggregate(promedio=Avg('calificacion'), total=Count('id'))

    margen = None
    if producto.precio_venta:
        margen = round((producto.precio_venta - producto.precio_compra) * 100 / producto.precio_venta)

    contexto = {
        'producto': producto,
        'imagen': producto.imagenes.filter(activo=True, es_principal=True).first(),
        'vendidos': vendidos, 'resenas': resenas, 'margen': margen,
        'movimientos': producto.movimientos.select_related('usuario')[:8],
        'puede_editar': tiene_permiso(request, 'productos.editar'),
    }
    return render(request, 'productos/detalle.html', contexto)


def _guardar_imagen(producto, imagen):
    """La foto anterior no se borra: deja de ser la principal y se deshabilita."""
    producto.imagenes.filter(es_principal=True, activo=True).update(es_principal=False, activo=False)
    ProductoImagen.objects.create(producto=producto, ruta=imagen, es_principal=True)


@requiere_permiso('productos.crear')
def crear_producto(request):
    form = ProductoForm(request.POST or None, request.FILES or None, crear=True)

    if request.method == 'POST':
        def guardar(form):
            producto = form.save()
            if form.cleaned_data['stock']:
                registrar_movimiento(producto, MovimientoInventario.Tipo.ENTRADA, form.cleaned_data['stock'],
                                     usuario=usuario_actual(request), motivo='Stock inicial')
            if form.cleaned_data.get('imagen'):
                _guardar_imagen(producto, form.cleaned_data['imagen'])
            return producto

        producto = validar_en_transaccion(form, guardar)
        if producto:
            return guardado(request, reverse('productos'), f'Producto "{producto.nombre}" agregado.')

    return mostrar_formulario(request, {
        'form': form, 'titulo': 'Agregar producto', 'icono': 'fa-circle-plus', 'ancho': 'lg',
        'texto_boton': 'Guardar producto', 'volver_url': reverse('productos'),
    })


@requiere_permiso('productos.editar')
def editar_producto(request, pk):
    producto = get_object_or_404(Producto.objects.select_related('marca'), pk=pk)
    form = ProductoForm(request.POST or None, request.FILES or None, instance=producto)
    if not tiene_permiso(request, 'productos.habilitar'):
        form.fields['activo'].disabled = True

    if request.method == 'POST':
        stock_antes = producto.stock_actual

        def guardar(form):
            # Solo se guardan los campos del formulario: el stock lo cambia registrar_movimiento()
            producto = form.save(commit=False)
            producto.save(update_fields=[c for c in ProductoForm.Meta.fields if c in form.fields])
            cambio = form.cleaned_data['stock'] - stock_antes
            if cambio:
                registrar_movimiento(producto, MovimientoInventario.Tipo.AJUSTE, cambio,
                                     usuario=usuario_actual(request), motivo='Ajuste desde Editar producto')
            if form.cleaned_data.get('imagen'):
                _guardar_imagen(producto, form.cleaned_data['imagen'])
            return producto

        try:
            guardado_ok = validar_en_transaccion(form, guardar)
        except ErrorDeNegocio as error:
            form.add_error('stock', str(error))
            guardado_ok = None
        if guardado_ok:
            return guardado(request, reverse('producto_detalle', args=[producto.pk]),
                            f'Se guardaron los cambios de "{guardado_ok.nombre}".')

    imagen = producto.imagenes.filter(activo=True, es_principal=True).first()
    return mostrar_formulario(request, {
        'form': form, 'titulo': 'Editar producto', 'subtitulo': f'{producto.sku} · {producto.nombre}',
        'icono': 'fa-pen-to-square', 'ancho': 'lg', 'imagen_actual': imagen.ruta.url if imagen else '',
        'volver_url': reverse('producto_detalle', args=[producto.pk]),
    })
