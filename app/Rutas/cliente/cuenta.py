from django.shortcuts import render

from . import datos
from .contexto import contexto_cliente


def mi_cuenta(request):
    contexto = contexto_cliente(request, seccion='cuenta')
    puntos = contexto['cliente']['puntos']
    contexto.update({
        'puntos': puntos,
        'pedidos': datos.pedidos_recientes(),
        'recomendaciones': datos.productos_recomendados(),
        'metas': datos.metas_de_puntos(puntos),
    })
    return render(request, 'cliente/cuenta/mi_cuenta.html', contexto)
