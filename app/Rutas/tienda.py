"""Vistas de la tienda (lado del cliente).

Por ahora usan datos de ejemplo definidos aquí. Cuando existan los modelos
(Producto, Pedido, Cliente...), solo hay que reemplazar estas listas por
consultas; las plantillas ya recorren los datos con bucles.
"""
from datetime import date

from django.shortcuts import render


# Categorías del menú "Todas las categorías" (se muestran en todas las páginas de la tienda)
CATEGORIAS = [
    {'nombre': 'Maquillaje', 'icono': 'fa-palette',
     'subcategorias': ['Ojos', 'Rostro', 'Labios', 'Uñas']},
    {'nombre': 'Cuidado de la piel', 'icono': 'fa-spa',
     'subcategorias': ['Limpiadores', 'Hidratantes', 'Serums', 'Protector solar']},
    {'nombre': 'Cuidado del cabello', 'icono': 'fa-pump-soap',
     'subcategorias': ['Shampoo', 'Acondicionadores', 'Aceites y serums']},
    {'nombre': 'Fragancias', 'icono': 'fa-spray-can-sparkles',
     'subcategorias': ['Perfumes', 'Body mists']},
    {'nombre': 'Brochas y accesorios', 'icono': 'fa-paintbrush',
     'subcategorias': ['Brochas', 'Esponjas', 'Cosmetiqueras']},
    {'nombre': 'Sets y regalos', 'icono': 'fa-gift',
     'subcategorias': ['Kits', 'Ediciones especiales']},
]

# Colores de la etiqueta de estado de cada pedido
CLASES_ESTADO = {
    'Entregado': 'bg-rosa-500 text-white',
    'En camino': 'bg-amber-100 text-amber-800',
    'Procesando': 'bg-sky-100 text-sky-800',
    'Cancelado': 'bg-gray-100 text-gray-600',
}


def _estrellas(calificacion):
    """Convierte 4.5 en ['llena', 'llena', 'llena', 'llena', 'media']."""
    llenas = int(calificacion)
    media = 1 if calificacion - llenas >= 0.5 else 0
    return ['llena'] * llenas + ['media'] * media + ['vacia'] * (5 - llenas - media)


def contexto_tienda(request):
    """Datos que necesita la plantilla base de la tienda (cabecera y menú lateral)."""
    return {
        'cliente': {'nombre': 'Vanessa', 'correo': 'vanessa@email.com'},
        'categorias': CATEGORIAS,
        'total_favoritos': 10,
        'total_carrito': 3,
    }


def mi_cuenta(request):
    puntos = 120

    pedidos = [
        {'marca': 'Maybelline', 'producto': 'Sky High Máscara', 'icono': 'fa-eye',
         'fecha': date(2025, 9, 22), 'estado': 'En camino'},
        {'marca': 'Fenty Beauty', 'producto': 'Gloss Bomb', 'icono': 'fa-droplet',
         'fecha': date(2025, 9, 15), 'estado': 'Entregado'},
        {'marca': 'Rare Beauty', 'producto': 'Rubor líquido', 'icono': 'fa-heart',
         'fecha': date(2025, 9, 15), 'estado': 'Entregado'},
        {'marca': 'Kérastase', 'producto': 'Aceite capilar', 'icono': 'fa-pump-soap',
         'fecha': date(2025, 9, 15), 'estado': 'Entregado'},
    ]
    for pedido in pedidos:
        pedido['clase_estado'] = CLASES_ESTADO.get(pedido['estado'], CLASES_ESTADO['Cancelado'])

    recomendaciones = [
        {'id': 1, 'marca': 'Maybelline', 'nombre': 'SuperStay Matte Ink', 'icono': 'fa-wand-magic-sparkles',
         'precio': 180, 'calificacion': 4.5, 'resenas': 124, 'favorito': True},
        {'id': 2, 'marca': 'Rare Beauty', 'nombre': 'Soft Pinch Blush', 'icono': 'fa-circle',
         'precio': 430, 'calificacion': 4.5, 'resenas': 56, 'favorito': True},
        {'id': 3, 'marca': 'Real Techniques', 'nombre': 'Set de brochas', 'icono': 'fa-paintbrush',
         'precio': 250, 'calificacion': 4.5, 'resenas': 72, 'favorito': False},
        {'id': 4, 'marca': 'The Ordinary', 'nombre': 'Hyaluronic Acid Serum', 'icono': 'fa-flask',
         'precio': 280, 'calificacion': 4.5, 'resenas': 58, 'favorito': False},
    ]
    for producto in recomendaciones:
        producto['estrellas'] = _estrellas(producto['calificacion'])

    metas = [
        {'icono': 'fa-truck-fast', 'texto': 'Envío gratis en tu próximo pedido', 'meta': 150},
        {'icono': 'fa-gift', 'texto': 'Regalo por 200 puntos', 'meta': 200},
    ]
    for meta in metas:
        meta['porcentaje'] = min(100, puntos * 100 // meta['meta'])
        meta['faltan'] = max(0, meta['meta'] - puntos)

    contexto = {
        **contexto_tienda(request),
        'seccion': 'cuenta',
        'puntos': puntos,
        'pedidos': pedidos,
        'recomendaciones': recomendaciones,
        'metas': metas,
    }
    return render(request, 'tienda/mi_cuenta.html', contexto)
