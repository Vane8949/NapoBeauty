"""Reportes con los datos reales de la base: indicadores, gráficas, tabla por tipo de reporte y exportación.

Notas:
  - Solo cuentan las ventas vigentes (Activo = 1); las anuladas no.
  - El costo de lo vendido se calcula con el precio de compra ACTUAL de cada producto,
    porque DetalleVenta no guarda el costo del momento de la venta.
"""
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Max, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from app.models import (
    Categoria, DetalleDevolucion, DetalleDevolucionProveedor, DetalleVenta, Devolucion, DevolucionProveedor, Producto,
    Venta, con_tonos,
)

from .comun import paginar, requiere_permiso, tiene_permiso

DINERO = DecimalField(max_digits=18, decimal_places=2)
COSTO = Sum(F('cantidad') * F('producto__precio_compra'), output_field=DINERO)
MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

TIPOS = [
    ('productos', 'Ventas por producto'),
    ('categorias', 'Ventas por categoría'),
    ('dias', 'Cierre de ventas por día'),
    ('clientes', 'Mejores clientes'),
    ('inventario', 'Inventario valorizado'),
    ('devoluciones', 'Devoluciones de clientes'),
    ('proveedores', 'Devoluciones a proveedores'),
]
RANGOS = [
    ('hoy', 'Hoy'), ('7d', 'Últimos 7 días'), ('mes', 'Este mes'), ('mes_pasado', 'Mes pasado'),
    ('90d', 'Últimos 90 días'), ('anio', 'Este año'), ('personalizado', 'Personalizado'),
]
FORMATOS = [('pantalla', 'Ver en pantalla'), ('csv', 'Excel (CSV)'), ('pdf', 'PDF (imprimir)')]


# -----------------------------------------------------------------------------
# Periodos
# -----------------------------------------------------------------------------

def mismo_dia(anio, mes, dia):
    """date(anio, mes, dia) sin pasarse del último día del mes."""
    siguiente = date(anio + (mes == 12), mes % 12 + 1, 1)
    return date(anio, mes, min(dia, (siguiente - timedelta(days=1)).day))


def leer_fecha(texto):
    try:
        return datetime.strptime(texto or '', '%Y-%m-%d').date()
    except ValueError:
        return None


def calcular_periodo(rango, desde_txt, hasta_txt, hoy):
    """(desde, hasta, desde_anterior, hasta_anterior, rango_usado). Se compara con un periodo equivalente anterior."""
    if rango == 'personalizado':
        desde, hasta = leer_fecha(desde_txt), leer_fecha(hasta_txt)
        if desde or hasta:
            desde, hasta = desde or hasta, hasta or desde
            if desde > hasta:
                desde, hasta = hasta, desde
        else:
            rango = 'mes'
    if rango == 'hoy':
        desde = hasta = hoy
    elif rango == '7d':
        desde, hasta = hoy - timedelta(days=6), hoy
    elif rango == '90d':
        desde, hasta = hoy - timedelta(days=89), hoy
    elif rango == 'mes_pasado':
        hasta = hoy.replace(day=1) - timedelta(days=1)
        desde = hasta.replace(day=1)
        hasta_ant = desde - timedelta(days=1)
        return desde, hasta, hasta_ant.replace(day=1), hasta_ant, rango
    elif rango == 'anio':
        desde, hasta = hoy.replace(month=1, day=1), hoy
        return desde, hasta, desde.replace(year=desde.year - 1), mismo_dia(hoy.year - 1, hoy.month, hoy.day), rango
    elif rango != 'personalizado':
        rango = 'mes'
        desde, hasta = hoy.replace(day=1), hoy
        # mismos días del mes anterior
        anterior = desde - timedelta(days=1)
        return desde, hasta, anterior.replace(day=1), mismo_dia(anterior.year, anterior.month, hoy.day), rango
    dias = (hasta - desde).days + 1
    return desde, hasta, desde - timedelta(days=dias), desde - timedelta(days=1), rango


# -----------------------------------------------------------------------------
# Consultas
# -----------------------------------------------------------------------------

def filtro_categoria(categoria, campo='producto'):
    """Productos de la categoría o de sus subcategorías."""
    if categoria is None:
        return Q()
    return Q(**{f'{campo}__categoria_id': categoria.pk}) | Q(**{f'{campo}__categoria__categoria_padre_id': categoria.pk})


def lineas_vendidas(desde, hasta, categoria):
    return DetalleVenta.objects.filter(
        filtro_categoria(categoria), venta__activo=True, venta__fecha__date__gte=desde, venta__fecha__date__lte=hasta)


def resumen(desde, hasta, categoria):
    """Indicadores de un periodo."""
    lineas = lineas_vendidas(desde, hasta, categoria).aggregate(
        ingresos=Sum('subtotal'), costo=COSTO, unidades=Sum('cantidad'))
    if categoria is None:
        ventas = Venta.objects.filter(activo=True, fecha__date__gte=desde, fecha__date__lte=hasta).aggregate(
            ingresos=Sum('total'), cantidad=Count('id'))
        ingresos, cantidad = ventas['ingresos'] or Decimal('0'), ventas['cantidad']
    else:
        ingresos = lineas['ingresos'] or Decimal('0')
        cantidad = lineas_vendidas(desde, hasta, categoria).values('venta_id').distinct().count()

    devueltas = DetalleDevolucion.objects.filter(
        filtro_categoria(categoria, 'detalle_venta__producto'), devolucion__activo=True,
        devolucion__fecha_solicitud__date__gte=desde, devolucion__fecha_solicitud__date__lte=hasta,
    ).exclude(devolucion__estado=Devolucion.Estado.RECHAZADA)
    reembolsadas = Q(devolucion__tipo_resolucion=Devolucion.TipoResolucion.REEMBOLSO,
                     devolucion__estado__in=[Devolucion.Estado.APROBADA, Devolucion.Estado.COMPLETADA])
    if categoria is None:
        reembolsos = Devolucion.objects.filter(
            activo=True, tipo_resolucion=Devolucion.TipoResolucion.REEMBOLSO,
            estado__in=[Devolucion.Estado.APROBADA, Devolucion.Estado.COMPLETADA],
            fecha_solicitud__date__gte=desde, fecha_solicitud__date__lte=hasta,
        ).aggregate(t=Sum('monto_reembolso'))['t']
    else:   # con categoría se valora lo devuelto al precio pagado
        reembolsos = devueltas.filter(reembolsadas).aggregate(
            t=Sum(F('cantidad') * F('detalle_venta__precio_unitario'), output_field=DINERO))['t']
    reembolsos = reembolsos or Decimal('0')
    unidades = lineas['unidades'] or 0
    unidades_devueltas = devueltas.aggregate(t=Sum('cantidad'))['t'] or 0
    costo = lineas['costo'] or Decimal('0')
    return {
        'ingresos': ingresos, 'costo': costo, 'reembolsos': reembolsos, 'ganancia': ingresos - costo - reembolsos,
        'ventas': cantidad, 'unidades': unidades, 'unidades_devueltas': unidades_devueltas,
        'ticket': ingresos / cantidad if cantidad else Decimal('0'),
        'tasa_devolucion': round(Decimal(unidades_devueltas) * 100 / unidades, 1) if unidades else None,
    }


def variacion(actual, anterior):
    actual, anterior = Decimal(actual or 0), Decimal(anterior or 0)
    if anterior == 0:
        return {'nuevo': True, 'sube': True} if actual > 0 else None
    cambio = round((actual - anterior) * 100 / abs(anterior))
    return {'valor': abs(cambio), 'sube': cambio >= 0}


def ultimos_meses(hoy, categoria, cantidad=6):
    """Ingresos y costo de lo vendido de los últimos meses (el actual incluido)."""
    etiquetas, ingresos, costos = [], [], []
    for atras in range(cantidad - 1, -1, -1):
        mes_total = hoy.year * 12 + hoy.month - 1 - atras
        anio, mes = divmod(mes_total, 12)
        inicio = date(anio, mes + 1, 1)
        fin = mismo_dia(anio, mes + 1, 31)
        lineas = lineas_vendidas(inicio, fin, categoria).aggregate(ingresos=Sum('subtotal'), costo=COSTO)
        if categoria is None:   # lo cobrado (con descuentos y envío), igual que la tarjeta de ingresos
            lineas['ingresos'] = Venta.objects.filter(activo=True, fecha__date__gte=inicio, fecha__date__lte=fin) \
                                              .aggregate(t=Sum('total'))['t']
        etiquetas.append(f'{MESES[mes]} {str(anio)[2:]}')
        ingresos.append(float(lineas['ingresos'] or 0))
        costos.append(float(lineas['costo'] or 0))
    return {'etiquetas': etiquetas, 'ingresos': ingresos, 'costos': costos}


def por_categoria_principal(lineas):
    """Agrupa líneas de venta en la categoría principal (la subcategoría cuenta para su grupo)."""
    grupos = {}
    filas = lineas.values(
        'producto__categoria__nombre', 'producto__categoria__categoria_padre__nombre',
    ).annotate(unidades=Sum('cantidad'), ingresos=Sum('subtotal'), costo=COSTO)
    for f in filas:
        nombre = f['producto__categoria__categoria_padre__nombre'] or f['producto__categoria__nombre']
        g = grupos.setdefault(nombre, {'categoria': nombre, 'unidades': 0, 'ingresos': Decimal('0'), 'costo': Decimal('0')})
        g['unidades'] += f['unidades'] or 0
        g['ingresos'] += f['ingresos'] or 0
        g['costo'] += f['costo'] or 0
    return sorted(grupos.values(), key=lambda g: g['ingresos'], reverse=True)


# -----------------------------------------------------------------------------
# Tablas de cada tipo de reporte: (columnas, filas, totales)
# columna = (clave, título, tipo) con tipo: texto | numero | dinero | porcentaje | fecha
# -----------------------------------------------------------------------------

def margen(ganancia, ingresos):
    return round(ganancia * 100 / ingresos, 1) if ingresos else None


def tabla_productos(desde, hasta, categoria):
    columnas = [('producto', 'Producto', 'texto'), ('sku', 'SKU', 'texto'), ('categoria', 'Categoría', 'texto'),
                ('unidades', 'Unidades', 'numero'), ('ingresos', 'Ingresos', 'dinero'), ('costo', 'Costo', 'dinero'),
                ('ganancia', 'Ganancia', 'dinero'), ('margen', 'Margen', 'porcentaje')]
    filas = []
    for f in (lineas_vendidas(desde, hasta, categoria)
              .values('producto_id', 'producto__nombre', 'producto__sku', 'producto__categoria__nombre')
              .annotate(unidades=Sum('cantidad'), ingresos=Sum('subtotal'), costo=COSTO).order_by('-ingresos')):
        ganancia = (f['ingresos'] or 0) - (f['costo'] or 0)
        filas.append({'producto': f['producto__nombre'], 'sku': f['producto__sku'],
                      'categoria': f['producto__categoria__nombre'], 'unidades': f['unidades'],
                      'ingresos': f['ingresos'], 'costo': f['costo'], 'ganancia': ganancia,
                      'margen': margen(ganancia, f['ingresos'])})
    return columnas, filas, sumar(filas, ['unidades', 'ingresos', 'costo', 'ganancia'], margen_de=('ganancia', 'ingresos'))


def tabla_categorias(desde, hasta, categoria):
    columnas = [('categoria', 'Categoría', 'texto'), ('unidades', 'Unidades', 'numero'),
                ('ingresos', 'Ingresos', 'dinero'), ('costo', 'Costo', 'dinero'), ('ganancia', 'Ganancia', 'dinero'),
                ('margen', 'Margen', 'porcentaje'), ('participacion', '% de las ventas', 'porcentaje')]
    filas = por_categoria_principal(lineas_vendidas(desde, hasta, categoria))
    total = sum(f['ingresos'] for f in filas)
    for f in filas:
        f['ganancia'] = f['ingresos'] - f['costo']
        f['margen'] = margen(f['ganancia'], f['ingresos'])
        f['participacion'] = round(f['ingresos'] * 100 / total, 1) if total else None
    return columnas, filas, sumar(filas, ['unidades', 'ingresos', 'costo', 'ganancia'], margen_de=('ganancia', 'ingresos'))


def tabla_dias(desde, hasta, categoria):
    columnas = [('fecha', 'Fecha', 'fecha'), ('ventas', 'N.º de ventas', 'numero'), ('unidades', 'Unidades', 'numero'),
                ('ingresos', 'Ingresos', 'dinero'), ('ticket', 'Ticket promedio', 'dinero')]
    dias = {}
    lineas = lineas_vendidas(desde, hasta, categoria).values_list('venta_id', 'venta__fecha', 'cantidad', 'subtotal')
    for venta_id, fecha, cantidad, subtotal in lineas:
        d = dias.setdefault(fecha.date(), {'fecha': fecha.date(), 'ids': set(), 'unidades': 0, 'ingresos': Decimal('0')})
        d['ids'].add(venta_id)
        d['unidades'] += cantidad
        d['ingresos'] += subtotal or 0
    if categoria is None:     # sin filtro, el ingreso del día es lo que se cobró (con descuentos y envío)
        for d in dias.values():
            d['ingresos'] = Decimal('0')
        ventas = Venta.objects.filter(activo=True, fecha__date__gte=desde, fecha__date__lte=hasta)
        for venta_id, fecha, total in ventas.values_list('id', 'fecha', 'total'):
            d = dias.setdefault(fecha.date(), {'fecha': fecha.date(), 'ids': set(), 'unidades': 0, 'ingresos': Decimal('0')})
            d['ids'].add(venta_id)
            d['ingresos'] += total or 0
    filas = []
    for fecha in sorted(dias, reverse=True):
        d = dias[fecha]
        n = len(d['ids'])
        filas.append({'fecha': fecha, 'ventas': n, 'unidades': d['unidades'], 'ingresos': d['ingresos'],
                      'ticket': d['ingresos'] / n if n else None})
    totales = sumar(filas, ['ventas', 'unidades', 'ingresos'])
    if totales and totales['ventas']:
        totales['ticket'] = totales['ingresos'] / totales['ventas']
    return columnas, filas, totales


def tabla_clientes(desde, hasta, categoria):
    columnas = [('cliente', 'Cliente', 'texto'), ('contacto', 'Contacto', 'texto'), ('compras', 'Compras', 'numero'),
                ('total', 'Total comprado', 'dinero'), ('ticket', 'Ticket promedio', 'dinero'),
                ('ultima', 'Última compra', 'fecha'), ('puntos', 'Puntos', 'numero')]
    ventas = Venta.objects.filter(activo=True, cliente__isnull=False, fecha__date__gte=desde, fecha__date__lte=hasta)
    if categoria is not None:
        # con subconsulta (no con join) para no sumar dos veces una venta con varios productos de la categoría
        ventas = ventas.filter(id__in=DetalleVenta.objects.filter(filtro_categoria(categoria)).values('venta_id'))
    filas = []
    for f in (ventas.values('cliente_id', 'cliente__nombre', 'cliente__apellido', 'cliente__telefono',
                            'cliente__correo', 'cliente__puntos_disponibles')
              .annotate(compras=Count('id'), total=Sum('total'), ultima=Max('fecha'))
              .order_by('-total')):
        filas.append({'cliente': f'{f["cliente__nombre"]} {f["cliente__apellido"] or ""}'.strip(),
                      'contacto': f['cliente__telefono'] or f['cliente__correo'] or '',
                      'compras': f['compras'], 'total': f['total'], 'ticket': (f['total'] or 0) / f['compras'],
                      'ultima': f['ultima'].date() if f['ultima'] else None,
                      'puntos': f['cliente__puntos_disponibles']})
    return columnas, filas, sumar(filas, ['compras', 'total'])


def tabla_inventario(desde, hasta, categoria):
    columnas = [('producto', 'Producto', 'texto'), ('sku', 'SKU', 'texto'), ('categoria', 'Categoría', 'texto'),
                ('stock', 'Stock', 'numero'), ('minimo', 'Mínimo', 'numero'), ('costo', 'Costo unitario', 'dinero'),
                ('valor_costo', 'Valor al costo', 'dinero'), ('valor_venta', 'Valor a precio de venta', 'dinero'),
                ('estado', 'Estado', 'texto')]
    filas = []
    productos = Producto.objects.filter(activo=True)
    if categoria is not None:
        productos = productos.filter(Q(categoria_id=categoria.pk) | Q(categoria__categoria_padre_id=categoria.pk))
    for p in con_tonos(productos).select_related('categoria').order_by('nombre'):
        estado = 'Agotado' if p.stock_actual == 0 else 'Bajo stock' if p.stock_bajo else 'En stock'
        filas.append({'producto': p.nombre, 'sku': p.sku, 'categoria': p.categoria.nombre, 'stock': p.stock_actual,
                      'minimo': p.stock_minimo, 'costo': p.precio_compra, 'valor_costo': p.precio_compra * p.stock_actual,
                      'valor_venta': p.precio_venta * p.stock_actual, 'estado': estado})
    return columnas, filas, sumar(filas, ['stock', 'valor_costo', 'valor_venta'])


def tabla_devoluciones(desde, hasta, categoria):
    columnas = [('numero', '#', 'texto'), ('fecha', 'Fecha', 'fecha'), ('venta', 'Venta', 'texto'),
                ('cliente', 'Cliente', 'texto'), ('motivo', 'Motivo', 'texto'), ('resolucion', 'Resolución', 'texto'),
                ('unidades', 'Unidades', 'numero'), ('monto', 'Monto reembolso', 'dinero'), ('estado', 'Estado', 'texto')]
    devoluciones = Devolucion.objects.filter(fecha_solicitud__date__gte=desde, fecha_solicitud__date__lte=hasta)
    if categoria is not None:
        devoluciones = devoluciones.filter(id__in=DetalleDevolucion.objects.filter(
            filtro_categoria(categoria, 'detalle_venta__producto')).values('devolucion_id'))
    unidades = dict(DetalleDevolucion.objects.filter(devolucion__in=devoluciones.values('id'))
                    .values('devolucion_id').annotate(t=Sum('cantidad')).values_list('devolucion_id', 't'))
    filas = []
    for d in devoluciones.select_related('venta__cliente').order_by('-fecha_solicitud', '-id'):
        filas.append({'numero': f'#{d.pk}', 'fecha': d.fecha_solicitud.date(), 'venta': d.venta.numero_factura,
                      'cliente': str(d.venta.cliente) if d.venta.cliente_id else 'Cliente de mostrador',
                      'motivo': d.get_motivo_display(), 'resolucion': d.get_tipo_resolucion_display(),
                      'unidades': unidades.get(d.pk, 0), 'monto': d.monto_reembolso,
                      'estado': d.get_estado_display() if d.activo else 'Anulada'})
    return columnas, filas, sumar(filas, ['unidades', 'monto'])


def tabla_proveedores(desde, hasta, categoria):
    columnas = [('numero', '#', 'texto'), ('fecha', 'Fecha', 'fecha'), ('proveedor', 'Proveedor', 'texto'),
                ('origen', 'Origen', 'texto'), ('motivo', 'Motivo', 'texto'), ('unidades', 'Unidades', 'numero'),
                ('costo', 'Costo', 'dinero'), ('resolucion', 'Resolución', 'texto'),
                ('acreditado', 'Acreditado', 'dinero'), ('estado', 'Estado', 'texto')]
    devoluciones = DevolucionProveedor.objects.filter(fecha__date__gte=desde, fecha__date__lte=hasta)
    if categoria is not None:
        devoluciones = devoluciones.filter(id__in=DetalleDevolucionProveedor.objects.filter(
            filtro_categoria(categoria)).values('devolucion_proveedor_id'))
    totales = {f['devolucion_proveedor_id']: f for f in DetalleDevolucionProveedor.objects.filter(
        devolucion_proveedor__in=devoluciones.values('id')).values('devolucion_proveedor_id').annotate(
        unidades=Sum('cantidad'), costo=Sum('subtotal'))}
    filas = []
    for d in devoluciones.select_related('proveedor').order_by('-fecha', '-id'):
        t = totales.get(d.pk, {})
        filas.append({'numero': f'#{d.pk}', 'fecha': d.fecha.date(), 'proveedor': d.proveedor.nombre_empresa,
                      'origen': d.get_origen_display(), 'motivo': d.get_motivo_display(),
                      'unidades': t.get('unidades') or 0, 'costo': t.get('costo') or 0,
                      'resolucion': d.get_resolucion_display(), 'acreditado': d.monto_credito,
                      'estado': d.get_estado_display() if d.activo else 'Anulada'})
    return columnas, filas, sumar(filas, ['unidades', 'costo', 'acreditado'])


def sumar(filas, claves, margen_de=None):
    if not filas:
        return None
    totales = {c: sum((f[c] or 0) for f in filas) for c in claves}
    if margen_de:
        totales['margen'] = margen(totales[margen_de[0]], totales[margen_de[1]])
    return totales


TABLAS = {
    'productos': tabla_productos, 'categorias': tabla_categorias, 'dias': tabla_dias, 'clientes': tabla_clientes,
    'inventario': tabla_inventario, 'devoluciones': tabla_devoluciones, 'proveedores': tabla_proveedores,
}


# -----------------------------------------------------------------------------
# Vista
# -----------------------------------------------------------------------------

def exportar_csv(nombre, titulo, periodo, columnas, filas, totales):
    """CSV que Excel abre con acentos (UTF-8 con BOM)."""
    respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
    respuesta['Content-Disposition'] = f'attachment; filename="{nombre}.csv"'
    respuesta.write('﻿')
    escritor = csv.writer(respuesta)
    escritor.writerow([f'Napo Beauty - {titulo}'])
    escritor.writerow([periodo])
    escritor.writerow([])
    escritor.writerow([titulo_col for _, titulo_col, _ in columnas])

    def valor(fila, clave, tipo):
        v = fila.get(clave)
        if v is None:
            return ''
        if tipo == 'fecha':
            return v.strftime('%d/%m/%Y')
        if tipo in ('dinero', 'porcentaje'):
            return f'{Decimal(v):.2f}' if tipo == 'dinero' else f'{v}'
        return v

    for fila in filas:
        escritor.writerow([valor(fila, c, t) for c, _, t in columnas])
    if totales:
        escritor.writerow([('TOTAL' if i == 0 else valor(totales, c, t)) for i, (c, _, t) in enumerate(columnas)])
    return respuesta


@requiere_permiso('reportes.ver')
def panel_reportes(request):
    ahora = timezone.now()
    hoy = ahora.date()
    tipo = request.GET.get('tipo') if request.GET.get('tipo') in dict(TIPOS) else 'productos'
    formato = request.GET.get('formato') if request.GET.get('formato') in dict(FORMATOS) else 'pantalla'
    desde, hasta, desde_ant, hasta_ant, rango = calcular_periodo(
        request.GET.get('rango', 'mes'), request.GET.get('desde'), request.GET.get('hasta'), hoy)
    categorias = Categoria.objects.filter(activo=True, categoria_padre__isnull=True).order_by('orden', 'nombre')
    categoria_id = request.GET.get('categoria', '')
    categoria = categorias.filter(pk=categoria_id).first() if categoria_id.isdigit() else None

    titulo = dict(TIPOS)[tipo] + (f' · {categoria.nombre}' if categoria else '')
    texto_periodo = (f'Del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}' if desde != hasta else f'{desde:%d/%m/%Y}')
    if tipo == 'inventario':
        texto_periodo = f'Existencias al {hoy:%d/%m/%Y}'
    columnas, filas, totales = TABLAS[tipo](desde, hasta, categoria)

    puede_exportar = tiene_permiso(request, 'reportes.exportar')
    if formato == 'csv' and puede_exportar:
        nombre = f'napobeauty_{tipo}_{desde:%Y%m%d}_{hasta:%Y%m%d}'
        return exportar_csv(nombre, titulo, texto_periodo, columnas, filas, totales)

    actual = resumen(desde, hasta, categoria)
    anterior = resumen(desde_ant, hasta_ant, categoria)
    tasa_dif = None
    if actual['tasa_devolucion'] is not None and anterior['tasa_devolucion'] is not None:
        tasa_dif = actual['tasa_devolucion'] - anterior['tasa_devolucion']

    vendidas = por_categoria_principal(lineas_vendidas(desde, hasta, categoria))
    pagina, filtros = paginar(request, filas, por_pagina=max(len(filas), 1) if formato == 'pdf' else 25)
    consulta = request.GET.copy()
    consulta.pop('pagina', None)
    consulta['formato'] = 'csv'
    url_csv = '?' + consulta.urlencode()
    consulta['formato'] = 'pdf'
    url_pdf = '?' + consulta.urlencode()

    return render(request, 'reportes/index.html', {
        'ahora': ahora, 'tipos': TIPOS, 'rangos': RANGOS, 'formatos': FORMATOS, 'categorias': categorias,
        'tipo': tipo, 'rango': rango, 'formato': formato, 'categoria': categoria,
        'desde': desde, 'hasta': hasta, 'desde_ant': desde_ant, 'hasta_ant': hasta_ant,
        'titulo': titulo, 'texto_periodo': texto_periodo,
        'kpi': actual, 'anterior': anterior,
        'var': {
            'ingresos': variacion(actual['ingresos'], anterior['ingresos']),
            'ganancia': variacion(actual['ganancia'], anterior['ganancia']),
            'costo': variacion(actual['costo'], anterior['costo']),
        },
        'tasa_dif': tasa_dif,
        'grafica_meses': ultimos_meses(hoy, categoria),
        'grafica_categorias': {'etiquetas': [c['categoria'] for c in vendidas],
                               'ingresos': [float(c['ingresos']) for c in vendidas]},
        'columnas': columnas, 'pagina': pagina, 'filtros': filtros, 'totales': totales, 'total_filas': len(filas),
        'puede_exportar': puede_exportar, 'url_csv': url_csv, 'url_pdf': url_pdf,
        'imprimir': formato == 'pdf',
    })
