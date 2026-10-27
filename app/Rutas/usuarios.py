from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from app.formularios import UsuarioForm
from app.models import Permiso, Rol, RolPermiso, Usuario

from .comun import filtrar_estado, guardado, mostrar_formulario, paginar, requiere_permiso, tiene_permiso

PERMISOS_VIGENTES = Q(rol__permisos_asignados__activo=True, rol__permisos_asignados__permiso__activo=True)


@requiere_permiso('usuarios.ver')
def panel_usuarios(request):
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')
    rol = request.GET.get('rol', '')

    usuarios = Usuario.objects.select_related('rol')
    if q:
        usuarios = usuarios.filter(Q(nombre__icontains=q) | Q(apellido__icontains=q) |
                                   Q(nombre_usuario__icontains=q) | Q(correo__icontains=q))
    if rol.isdigit():
        usuarios = usuarios.filter(rol_id=rol)
    usuarios = filtrar_estado(usuarios, estado).annotate(
        num_permisos=Count('rol__permisos_asignados', filter=PERMISOS_VIGENTES),
    ).order_by('nombre', 'apellido')
    pagina, filtros = paginar(request, usuarios)

    contexto = {
        'pagina': pagina, 'filtros': filtros, 'q': q, 'estado': estado, 'rol': rol,
        'busqueda': bool(q or estado or rol),
        'roles': Rol.objects.filter(activo=True),
        'total_permisos': Permiso.objects.filter(activo=True).count(),
        'kpi': {
            'total': Usuario.objects.count(),
            'administradores': Usuario.objects.filter(activo=True, rol__nombre='Administrador').count(),
            'cajeros': Usuario.objects.filter(activo=True).exclude(rol__nombre='Administrador').count(),
            'inactivos': Usuario.objects.filter(activo=False).count(),
        },
        'puede_editar': tiene_permiso(request, 'usuarios.editar'),
        'puede_crear': tiene_permiso(request, 'usuarios.crear'),
    }
    return render(request, 'usuarios/index.html', contexto)


@requiere_permiso('usuarios.ver')
def detalle_usuario(request, pk):
    usuario = get_object_or_404(Usuario.objects.select_related('rol'), pk=pk)
    asignados = (RolPermiso.objects.filter(rol=usuario.rol, activo=True, permiso__activo=True)
                 .select_related('permiso').order_by('permiso__modulo', 'permiso__id'))
    # Agrupa los permisos por módulo: {'productos': ['Ver', 'Editar', ...]}
    por_modulo = {}
    for asignado in asignados:
        por_modulo.setdefault(asignado.permiso.modulo, []).append(asignado.permiso.get_accion_display())
    return render(request, 'usuarios/detalle.html', {
        'usuario': usuario,
        'permisos': por_modulo,
        'ventas_registradas': usuario.ventas.filter(activo=True).count(),
        'puede_editar': tiene_permiso(request, 'usuarios.editar'),
    })


@requiere_permiso('usuarios.crear')
def crear_usuario(request):
    form = UsuarioForm(request.POST or None, crear=True)
    if request.method == 'POST' and form.is_valid():
        usuario = form.save()
        return guardado(request, reverse('usuarios'), f'Usuario {usuario} creado como {usuario.rol.nombre}.')
    return mostrar_formulario(request, {
        'form': form, 'titulo': 'Agregar usuario', 'icono': 'fa-user-plus', 'texto_boton': 'Crear usuario',
        'volver_url': reverse('usuarios'),
    })


@requiere_permiso('usuarios.editar')
def editar_usuario(request, pk):
    usuario = get_object_or_404(Usuario.objects.select_related('rol'), pk=pk)
    form = UsuarioForm(request.POST or None, instance=usuario)
    if not tiene_permiso(request, 'usuarios.habilitar'):
        form.fields['activo'].disabled = True

    if request.method == 'POST' and form.is_valid():
        usuario = form.save()
        texto = f'Se guardaron los datos de {usuario}.'
        if form.cleaned_data.get('nueva_contrasena'):
            texto += ' La contraseña fue cambiada.'
        return guardado(request, reverse('usuario_detalle', args=[usuario.pk]), texto)

    return mostrar_formulario(request, {
        'form': form, 'titulo': 'Editar usuario', 'icono': 'fa-user-pen',
        'subtitulo': f'@{usuario.nombre_usuario} · {usuario.rol.nombre}',
        'volver_url': reverse('usuario_detalle', args=[usuario.pk]),
        'resumen': [('Creado el', usuario.fecha_creacion.strftime('%d/%m/%Y')),
                    ('Último acceso', usuario.ultimo_acceso.strftime('%d/%m/%Y %H:%M')
                     if usuario.ultimo_acceso else 'Nunca')],
    })
