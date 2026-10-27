"""Filtros de plantilla del panel: {% load napo %}"""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def cordobas(valor):
    """1234.5 -> 'C$ 1,234.50'"""
    if valor in (None, ''):
        return 'C$ 0.00'
    try:
        return f'C$ {Decimal(valor):,.2f}'
    except (InvalidOperation, TypeError, ValueError):
        return valor


@register.filter
def iniciales(texto):
    """'Ana García' -> 'AG'"""
    partes = str(texto or '').split()
    return ''.join(p[0] for p in partes[:2]).upper() or '?'


@register.filter
def porcentaje(parte, total):
    """Porcentaje entero (0-100) para barras de progreso."""
    try:
        parte, total = float(parte), float(total)
    except (TypeError, ValueError):
        return 0
    if total <= 0:
        return 100 if parte > 0 else 0
    return max(0, min(100, round(parte * 100 / total)))


@register.filter
def celda(fila, columna):
    """Valor formateado de una celda de reporte. columna = (clave, título, tipo)."""
    if not fila:
        return ''
    clave, _, tipo = columna
    if clave not in fila:
        return ''
    valor = fila[clave]
    if valor is None or valor == '':
        return '—'
    if tipo == 'dinero':
        return cordobas(valor)
    if tipo == 'porcentaje':
        return f'{valor}%'
    if tipo == 'fecha':
        return valor.strftime('%d/%m/%Y')
    if tipo == 'numero':
        return f'{valor:,}'
    return valor
