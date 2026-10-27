"""Datos que necesita la plantilla base (cabecera y menú lateral) en todas las páginas del cliente."""
from . import datos


def contexto_cliente(request, seccion):
    """`seccion` marca como activo el enlace del menú lateral (ej. 'pedidos', 'favoritos')."""
    cliente = datos.cliente_actual()
    return {
        'cliente': cliente,
        'categorias': datos.CATEGORIAS,
        'total_favoritos': cliente['total_favoritos'],
        'total_carrito': cliente['total_carrito'],
        'seccion': seccion,
    }
