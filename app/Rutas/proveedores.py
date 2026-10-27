from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from app.formularios import ProveedorForm
from app.models import Compra, Producto, Proveedor

from .comun import filtrar_estado, guardado, mostrar_formulario, paginar, requiere_permiso, tiene_permiso


def _por_proveedor(consulta, campo):
    """Subconsulta agrupada por proveedor.

    SQL Server no permite mezclar en una misma consulta un conteo agrupado (GROUP BY)
    con subconsultas, así que todos los totales de la lista se calculan con subconsultas.
    """
    return Subquery(consulta.filter(proveedor=OuterRef('pk')).values('proveedor')
                    .annotate(valor=campo).values('valor')[:1])


def _de_compras(estado, campo):
    return _por_proveedor(Compra.objects.filter(activo=True, estado=estado), campo)


@requiere_permiso('proveedores.ver')
def panel_proveedores(request):
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')

    proveedores = Proveedor.objects.all()
    if q:
        con_marca = Proveedor.objects.filter(productos__marca__nombre__icontains=q).values('pk')
        proveedores = proveedores.filter(Q(nombre_empresa__icontains=q) | Q(nombre_contacto__icontains=q) |
                                         Q(ruc__icontains=q) | Q(pk__in=con_marca))
    proveedores = filtrar_estado(proveedores, estado).annotate(
        num_productos=Coalesce(_por_proveedor(Producto.objects.all(), Count('id')), 0,
                               output_field=IntegerField()),
        pendientes=Coalesce(_de_compras(Compra.Estado.PENDIENTE, Count('id')), 0, output_field=IntegerField()),
        total_comprado=_de_compras(Compra.Estado.RECIBIDA, Sum('total')),
    ).order_by('nombre_empresa')
    pagina, filtros = paginar(request, proveedores)

    inicio_mes = timezone.now().date().replace(day=1)
    compras = Compra.objects.filter(activo=True)
    contexto = {
        'pagina': pagina, 'filtros': filtros, 'q': q, 'estado': estado, 'busqueda': bool(q or estado),
        'kpi': {
            'total': Proveedor.objects.count(),
            'activos': Proveedor.objects.filter(activo=True).count(),
            'pendientes': compras.filter(estado=Compra.Estado.PENDIENTE).count(),
            'inversion_mes': compras.filter(estado=Compra.Estado.RECIBIDA, fecha__date__gte=inicio_mes)
                                    .aggregate(t=Sum('total'))['t'] or 0,
        },
        'puede_editar': tiene_permiso(request, 'proveedores.editar'),
        'puede_crear': tiene_permiso(request, 'proveedores.crear'),
    }
    return render(request, 'proveedores/index.html', contexto)


@requiere_permiso('proveedores.ver')
def detalle_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    resumen = proveedor.compras.filter(activo=True).aggregate(
        total=Sum('total', filter=Q(estado=Compra.Estado.RECIBIDA)),
        pendientes=Count('id', filter=Q(estado=Compra.Estado.PENDIENTE)))
    return render(request, 'proveedores/detalle.html', {
        'proveedor': proveedor,
        'productos': proveedor.productos.select_related('marca', 'categoria').order_by('nombre'),
        'compras': proveedor.compras.select_related('usuario').order_by('-fecha')[:10],
        'devoluciones': proveedor.devoluciones.order_by('-fecha', '-id')[:10],
        'resumen': resumen,
        'puede_editar': tiene_permiso(request, 'proveedores.editar'),
    })


@requiere_permiso('proveedores.crear')
def crear_proveedor(request):
    form = ProveedorForm(request.POST or None, crear=True)
    if request.method == 'POST' and form.is_valid():
        proveedor = form.save()
        return guardado(request, reverse('proveedores'), f'Proveedor {proveedor.nombre_empresa} registrado.')
    return mostrar_formulario(request, {
        'form': form, 'titulo': 'Registrar proveedor', 'icono': 'fa-truck-fast', 'texto_boton': 'Guardar proveedor',
        'volver_url': reverse('proveedores'),
    })


@requiere_permiso('proveedores.editar')
def editar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    form = ProveedorForm(request.POST or None, instance=proveedor)
    if not tiene_permiso(request, 'proveedores.habilitar'):
        form.fields['activo'].disabled = True

    if request.method == 'POST' and form.is_valid():
        proveedor = form.save()
        return guardado(request, reverse('proveedor_detalle', args=[proveedor.pk]),
                        f'Se guardaron los datos de {proveedor.nombre_empresa}.')

    return mostrar_formulario(request, {
        'form': form, 'titulo': 'Editar proveedor', 'icono': 'fa-pen-to-square', 'subtitulo': proveedor.nombre_empresa,
        'volver_url': reverse('proveedor_detalle', args=[proveedor.pk]),
    })
