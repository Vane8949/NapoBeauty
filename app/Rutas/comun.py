"""Herramientas compartidas por las pantallas del panel de administración."""
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render

from app.models import Usuario


def usuario_actual(request):
    """Usuario del panel que inició sesión (o None mientras no exista el inicio de sesión)."""
    if not hasattr(request, '_usuario_napo'):
        usuario_id = request.session.get('usuario_id')
        request._usuario_napo = (
            Usuario.objects.select_related('rol').filter(pk=usuario_id, activo=True).first()
            if usuario_id else None
        )
    return request._usuario_napo


def tiene_permiso(request, codigo):
    """True si el usuario actual tiene el permiso, ej. 'productos.editar'.

    El inicio de sesión todavía no está conectado: mientras no haya nadie en sesión
    y DEBUG sea True (desarrollo), se trabaja con permisos de administrador.
    """
    usuario = usuario_actual(request)
    if usuario is None:
        return settings.DEBUG
    return usuario.tiene_permiso(codigo)


def es_modal(request):
    """True cuando el formulario se pidió desde la ventana emergente (static/js/modales.js)."""
    return request.headers.get('X-Modal') == '1'


def requiere_permiso(codigo):
    """Decorador de vistas: sin el permiso, vuelve a la lista del módulo con un aviso."""
    modulo = codigo.split('.')[0]

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not tiene_permiso(request, codigo):
                texto = 'No tienes permiso para realizar esta acción.'
                if es_modal(request):
                    return JsonResponse({'ok': False, 'error': texto}, status=403)
                messages.error(request, texto)
                return redirect(modulo if codigo != f'{modulo}.ver' else 'dashboard')
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


def mostrar_formulario(request, contexto):
    """Dibuja el formulario dentro de la ventana emergente o, sin JavaScript, como página completa.

    Contexto: form, titulo, icono, accion (URL del POST), volver_url, texto_boton,
    y opcionales: subtitulo, resumen, ancho ('md', 'lg', 'xl'), imagen_actual, seccion_extra.
    """
    contexto.setdefault('accion', request.get_full_path())
    plantilla = 'componentes/formulario.html' if es_modal(request) else 'componentes/pagina_formulario.html'
    return render(request, plantilla, contexto)


def guardado(request, url, texto, nivel=messages.SUCCESS, ir=False):
    """Respuesta después de guardar: la ventana emergente recarga la página; sin ella, redirige.

    Con ir=True la ventana emergente abre url en lugar de recargar (ej. el recibo de una venta nueva).
    """
    messages.add_message(request, nivel, texto)
    if es_modal(request):
        return JsonResponse({'ok': True, 'url': url, 'ir': ir})
    return redirect(url)


class FormularioInvalido(Exception):
    """Se lanza dentro de una transacción para deshacer lo que el formulario alcanzó a crear."""


def validar_en_transaccion(form, guardar):
    """Valida y guarda en una sola transacción. Si el formulario no es válido, no queda nada a medias.

    guardar(form) hace el trabajo y devuelve lo que la vista necesite.
    """
    try:
        with transaction.atomic():
            if not form.is_valid():
                raise FormularioInvalido
            return guardar(form)
    except FormularioInvalido:
        return None


def paginar(request, queryset, por_pagina=15):
    """Devuelve la página pedida en ?pagina= y los demás filtros para armar los enlaces."""
    pagina = Paginator(queryset, por_pagina).get_page(request.GET.get('pagina'))
    filtros = request.GET.copy()
    filtros.pop('pagina', None)
    return pagina, filtros.urlencode()


def filtrar_estado(queryset, estado):
    """Filtro común del select 'Estado' (activos / inactivos / todos)."""
    if estado == 'activos':
        return queryset.filter(activo=True)
    if estado == 'inactivos':
        return queryset.filter(activo=False)
    return queryset
