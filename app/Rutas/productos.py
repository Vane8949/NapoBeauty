from django.db.models import Avg, Count, F, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from app.formularios import ProductoForm, UnirTonoForm
from app.models import Categoria, Producto, ProductoImagen, VarianteProducto, con_tonos
from app.servicios import ErrorDeNegocio, guardar_stock_unico, guardar_tonos, unir_como_tono

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
    productos = con_tonos(filtrar_estado(productos, estado)).order_by('nombre')
    pagina, filtros = paginar(request, productos)

    activos = Producto.objects.filter(activo=True)
    contexto = {
        'pagina': pagina, 'filtros': filtros, 'q': q, 'estado': estado, 'categoria': categoria,
        'busqueda': bool(q or estado or categoria),
        'categorias': Categoria.objects.filter(categoria_padre__isnull=True, activo=True),
        'kpi': {
            'total': Producto.objects.count(),
            'categorias': Categoria.objects.filter(activo=True).count(),
            'bajo_stock': VarianteProducto.objects.filter(activo=True, producto__activo=True,
                                                          stock_actual__lte=F('stock_minimo'))
                                                  .values('producto').distinct().count(),
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

    imagen = producto.imagenes.filter(activo=True, es_principal=True).first()
    tonos = [v for v in producto.variantes.all() if not v.es_unica]
    fotos_tonos = [v for v in tonos if v.imagen and v.activo]
    contexto = {
        'producto': producto,
        'imagen': imagen,
        'vendidos': vendidos, 'resenas': resenas, 'margen': margen,
        'movimientos': producto.movimientos.select_related('usuario', 'variante')[:8],
        'tonos': tonos,
        # Con tonos, la galería es la de los tonos (cada tono ya es el producto en ese color);
        # la foto propia del producto solo se usa si ningún tono tiene foto.
        'fotos_tonos': fotos_tonos,
        'foto_principal': fotos_tonos[0].imagen.url if fotos_tonos else (imagen.ruta.url if imagen else ''),
        'nombre_foto': fotos_tonos[0].nombre if fotos_tonos else '',
        'puede_editar': tiene_permiso(request, 'productos.editar'),
    }
    return render(request, 'productos/detalle.html', contexto)


def _guardar_stock(request, form, producto, motivo):
    """Stock del producto: en su variante 'Único' o, si tiene tonos, en cada tono."""
    if form.con_tonos:
        guardar_tonos(producto, form.tonos.filas, usuario=usuario_actual(request))
        _portada_desde_tonos(producto)
    else:
        guardar_stock_unico(producto, form.cleaned_data['stock'], form.cleaned_data['stock_minimo'],
                            usuario=usuario_actual(request), motivo=motivo)


def _portada_desde_tonos(producto):
    """Producto con tonos sin foto propia: su portada (listas, dashboard, tienda) es la foto del primer tono."""
    if producto.imagenes.filter(activo=True, es_principal=True).exists():
        return
    tono = producto.variantes.filter(activo=True).exclude(imagen='').exclude(imagen__isnull=True).first()
    if tono:
        ProductoImagen.objects.create(producto=producto, ruta=tono.imagen.name, es_principal=True)


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
            _guardar_stock(request, form, producto, motivo='Stock inicial')
            if form.cleaned_data.get('imagen') and not form.con_tonos:
                _guardar_imagen(producto, form.cleaned_data['imagen'])
            return producto

        try:
            producto = validar_en_transaccion(form, guardar)
        except ErrorDeNegocio as error:
            form.add_error(None, str(error))
            producto = None
        if producto:
            return guardado(request, reverse('productos'), f'Producto "{producto.nombre}" agregado.')

    return mostrar_formulario(request, {
        'form': form, 'titulo': 'Agregar producto', 'icono': 'fa-circle-plus', 'ancho': 'xl',
        'texto_boton': 'Guardar producto', 'volver_url': reverse('productos'),
        'tonos': form.tonos,
    })


@requiere_permiso('productos.editar')
def editar_producto(request, pk):
    producto = get_object_or_404(Producto.objects.select_related('marca'), pk=pk)
    form = ProductoForm(request.POST or None, request.FILES or None, instance=producto)
    if not tiene_permiso(request, 'productos.habilitar'):
        form.fields['activo'].disabled = True

    if request.method == 'POST':
        def guardar(form):
            # Solo se guardan los campos del formulario: el stock lo cambia registrar_movimiento()
            producto = form.save(commit=False)
            producto.save(update_fields=[c for c in ProductoForm.Meta.fields if c in form.fields])
            _guardar_stock(request, form, producto, motivo='Ajuste desde Editar producto')
            if form.cleaned_data.get('imagen') and not form.con_tonos:
                _guardar_imagen(producto, form.cleaned_data['imagen'])
            return producto

        try:
            guardado_ok = validar_en_transaccion(form, guardar)
        except ErrorDeNegocio as error:
            form.add_error(None, str(error))
            guardado_ok = None
        if guardado_ok:
            return guardado(request, reverse('producto_detalle', args=[producto.pk]),
                            f'Se guardaron los cambios de "{guardado_ok.nombre}".')

    imagen = producto.imagenes.filter(activo=True, es_principal=True).first()
    return mostrar_formulario(request, {
        'form': form, 'titulo': 'Editar producto', 'subtitulo': f'{producto.sku} · {producto.nombre}',
        'icono': 'fa-pen-to-square', 'ancho': 'xl', 'imagen_actual': imagen.ruta.url if imagen else '',
        'volver_url': reverse('producto_detalle', args=[producto.pk]),
        'tonos': form.tonos,
    })


@requiere_permiso('productos.editar')
def unir_tono(request, pk):
    """Unir otro producto (registrado aparte) como tono de este: pasa su stock, SKU, foto e historial."""
    producto = get_object_or_404(Producto.objects.select_related('marca'), pk=pk, activo=True)
    form = UnirTonoForm(request.POST or None, producto=producto)
    if request.method == 'POST' and form.is_valid():
        datos = form.cleaned_data
        try:
            tonos = unir_como_tono(producto, datos['origen'], datos.get('nombre_destino'), datos.get('nombre_origen'),
                                   usuario=usuario_actual(request))
        except ErrorDeNegocio as error:
            form.add_error(None, str(error))
        else:
            nombres = ', '.join(t.nombre for t in tonos)
            texto = f'"{datos["origen"].nombre}" quedó como tono {nombres} de este producto y se deshabilitó aparte.'
            for aviso in getattr(form, 'avisos', []):
                texto += ' ' + aviso
            return guardado(request, reverse('producto_detalle', args=[producto.pk]), texto)

    return mostrar_formulario(request, {
        'form': form, 'titulo': 'Unir producto como tono', 'icono': 'fa-palette',
        'subtitulo': f'{producto.sku} · {producto.nombre}', 'texto_boton': 'Unir como tono',
        'volver_url': reverse('producto_detalle', args=[producto.pk]),
        'resumen': [('Stock actual', producto.stock_actual), ('Precio', f'C$ {producto.precio_venta:,.2f}'),
                    ('Marca', producto.marca.nombre),
                    ('Tonos', producto.variantes.exclude(nombre=VarianteProducto.UNICA).count() or 'Sin tonos')],
    })

