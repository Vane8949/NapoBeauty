"""Datos de ejemplo de la vista cliente.

Mientras no existan los modelos (Producto, Pedido, Cliente...), las vistas toman
sus datos de aquí. Las plantillas ya recorren estas listas con bucles, así que
al crear los modelos solo hay que cambiar estas funciones por consultas.
"""
from datetime import date

# Menú "Todas las categorías"
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


def estrellas(calificacion):
    """Convierte 4.5 en ['llena', 'llena', 'llena', 'llena', 'media']."""
    llenas = int(calificacion)
    media = 1 if calificacion - llenas >= 0.5 else 0
    return ['llena'] * llenas + ['media'] * media + ['vacia'] * (5 - llenas - media)


def cliente_actual():
    return {'nombre': 'Vanessa', 'correo': 'vanessa@email.com', 'puntos': 120,
            'total_favoritos': 10, 'total_carrito': 3}


def pedidos_recientes():
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
    return pedidos


def productos_recomendados():
    # 'imagen' es opcional: ruta dentro de static/, ej. 'cliente/img/productos/matte-ink.png'
    productos = [
        {'id': 1, 'marca': 'Maybelline', 'nombre': 'SuperStay Matte Ink', 'icono': 'fa-wand-magic-sparkles',
         'precio': 180, 'calificacion': 4.5, 'resenas': 124, 'favorito': True},
        {'id': 2, 'marca': 'Rare Beauty', 'nombre': 'Soft Pinch Blush', 'icono': 'fa-circle',
         'precio': 430, 'calificacion': 4.5, 'resenas': 56, 'favorito': True},
        {'id': 3, 'marca': 'Real Techniques', 'nombre': 'Set de brochas', 'icono': 'fa-paintbrush',
         'precio': 250, 'calificacion': 4.5, 'resenas': 72, 'favorito': False},
        {'id': 4, 'marca': 'The Ordinary', 'nombre': 'Hyaluronic Acid Serum', 'icono': 'fa-flask',
         'precio': 280, 'calificacion': 4.5, 'resenas': 58, 'favorito': False},
    ]
    for producto in productos:
        producto['estrellas'] = estrellas(producto['calificacion'])
    return productos


def metas_de_puntos(puntos):
    metas = [
        {'icono': 'fa-truck-fast', 'texto': 'Envío gratis en tu próximo pedido', 'meta': 150},
        {'icono': 'fa-gift', 'texto': 'Regalo por 200 puntos', 'meta': 200},
    ]
    for meta in metas:
        meta['porcentaje'] = min(100, puntos * 100 // meta['meta'])
        meta['faltan'] = max(0, meta['meta'] - puntos)
    return metas
