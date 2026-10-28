"""Dashboard: resumen del negocio con los datos reales de la base."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Prefetch, Sum
from django.shortcuts import render
from django.utils import timezone

from app.models import Cliente, DetalleVenta, Producto, ProductoImagen, VarianteProducto, Venta

from .comun import tiene_permiso

DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
PEDIDOS_ABIERTOS = [Venta.Estado.PENDIENTE, Venta.Estado.PAGADA, Venta.Estado.PROCESANDO, Venta.Estado.EN_CAMINO]


def variacion(actual, anterior):
    """Cambio porcentual para las tarjetas: {'valor': 12, 'sube': True} o None si no se puede comparar."""
    actual, anterior = Decimal(actual or 0), Decimal(anterior or 0)
    if anterior == 0:
        return {'nuevo': True, 'sube': True} if actual > 0 else None
    cambio = round((actual - anterior) * 100 / anterior)
    return {'valor': abs(cambio), 'sube': cambio >= 0}


def mes_anterior(fecha):
    """Mismo día del mes anterior (o el último día si ese mes es más corto)."""
    primero = fecha.replace(day=1)
    ultimo_anterior = primero - timedelta(days=1)
    return ultimo_anterior.replace(day=min(fecha.day, ultimo_anterior.day))


def panel_principal(request):
    ahora = timezone.now()
    hoy = ahora.date()
    inicio_mes = hoy.replace(day=1)
    hoy_mes_pasado = mes_anterior(hoy)
    inicio_mes_pasado = hoy_mes_pasado.replace(day=1)

    vigentes = Venta.objects.filter(activo=True)

    # --- Tarjetas ---
    ventas_mes = vigentes.filter(fecha__date__gte=inicio_mes, fecha__date__lte=hoy).aggregate(
        total=Sum('total'), cantidad=Count('id'))
    # Se compara contra los mismos días del mes pasado (1 al día de hoy) para que sea justo
    ventas_pasado = vigentes.filter(fecha__date__gte=inicio_mes_pasado, fecha__date__lte=hoy_mes_pasado).aggregate(
        total=Sum('total'))['total']

    productos = Producto.objects.filter(activo=True)
    clientes = Cliente.objects.filter(activo=True)
    clientes_nuevos = clientes.filter(fecha_registro__date__gte=inicio_mes).count()
    clientes_nuevos_pasado = clientes.filter(fecha_registro__date__gte=inicio_mes_pasado,
                                             fecha_registro__date__lte=hoy_mes_pasado).count()
    pedidos = vigentes.filter(canal=Venta.Canal.EN_LINEA, estado__in=PEDIDOS_ABIERTOS)

    kpi = {
        'productos': productos.count(),
        'productos_nuevos': productos.filter(fecha_creacion__date__gte=inicio_mes).count(),
        'ventas_mes': ventas_mes['total'] or 0,
        'ventas_mes_cantidad': ventas_mes['cantidad'],
        'ventas_variacion': variacion(ventas_mes['total'], ventas_pasado),
        'clientes': clientes.count(),
        'clientes_nuevos': clientes_nuevos,
        'clientes_variacion': variacion(clientes_nuevos, clientes_nuevos_pasado),
        'pedidos_pendientes': pedidos.count(),
        'pedidos_en_camino': pedidos.filter(estado=Venta.Estado.EN_CAMINO).count(),
    }

    # --- Ventas de los últimos 7 días (monto y número de ventas por día) ---
    dias = [hoy - timedelta(days=i) for i in range(6, -1, -1)]
    montos = {d: Decimal('0') for d in dias}
    cantidades = {d: 0 for d in dias}
    for fecha, total in vigentes.filter(fecha__date__gte=dias[0], fecha__date__lte=hoy).values_list('fecha', 'total'):
        montos[fecha.date()] += total or 0
        cantidades[fecha.date()] += 1
    grafica_dias = {
        'etiquetas': ['Hoy' if d == hoy else f'{DIAS[d.weekday()]} {d.day}' for d in dias],
        'montos': [float(montos[d]) for d in dias],
        'cantidades': [cantidades[d] for d in dias],
    }
    total_semana = sum(montos.values())

    # --- Productos más vendidos (unidades, últimos 30 días) ---
    vendidos = list(
        DetalleVenta.objects.filter(venta__activo=True, venta__fecha__date__gt=hoy - timedelta(days=30))
        .values('producto_id', nombre=F('producto__nombre'))
        .annotate(unidades=Sum('cantidad')).order_by('-unidades', 'nombre')
    )
    top = vendidos[:5]
    otros = sum(v['unidades'] for v in vendidos[5:])
    grafica_top = {
        'etiquetas': [v['nombre'] for v in top] + (['Otros'] if otros else []),
        'unidades': [v['unidades'] for v in top] + ([otros] if otros else []),
    }

    # --- Listas ---
    # Bajo stock por tono: un labial puede tener el rojo agotado aunque queden otros tonos
    imagenes = Prefetch('producto__imagenes', queryset=ProductoImagen.objects.filter(activo=True), to_attr='fotos')
    bajo_stock = (VarianteProducto.objects.filter(activo=True, producto__activo=True,
                                                  stock_actual__lte=F('stock_minimo'))
                  .select_related('producto__marca').prefetch_related(imagenes)
                  .order_by('stock_actual', 'producto__nombre', 'orden'))

    contexto = {
        'ahora': ahora,
        'kpi': kpi,
        'grafica_dias': grafica_dias,
        'total_semana': total_semana,
        'grafica_top': grafica_top,
        'top_unidades': sum(grafica_top['unidades']),
        'ultimas_ventas': vigentes.select_related('cliente').order_by('-fecha', '-id')[:5],
        'pedidos_recientes': vigentes.filter(canal=Venta.Canal.EN_LINEA).select_related('cliente')
                                     .order_by('-fecha', '-id')[:5],
        'bajo_stock': bajo_stock[:5],
        'bajo_stock_total': bajo_stock.count(),
        'puede': {
            'productos': tiene_permiso(request, 'productos.crear'),
            'ventas': tiene_permiso(request, 'ventas.crear'),
            'inventario': tiene_permiso(request, 'inventario.ver'),
            'devoluciones': tiene_permiso(request, 'devoluciones.ver'),
            'reportes': tiene_permiso(request, 'reportes.ver'),
            'usuarios': tiene_permiso(request, 'usuarios.ver'),
        },
    }
    return render(request, 'dashboard/index.html', contexto)
