"""Datos disponibles en todas las plantillas del panel."""
from app.Rutas.comun import usuario_actual


def panel(request):
    # Primera parte de la URL: '/productos/5/editar/' -> 'productos' (marca el menú activo)
    seccion = request.path.strip('/').split('/')[0] if request.path else ''
    usuario = usuario_actual(request)
    return {
        'seccion': seccion,
        'usuario_panel': usuario,
        'nombre_panel': str(usuario) if usuario else 'Administrador',
    }
