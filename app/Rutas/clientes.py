from django.db.models import Avg, Count, Max, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from app.formularios import ClienteForm
from app.models import Cliente, Venta

from .comun import filtrar_estado, guardado, mostrar_formulario, paginar, requiere_permiso, tiene_permiso

VENTAS_VIGENTES = Q(ventas__activo=True)


def con_resumen_de_compras(clientes):
    return clientes.annotate(
        compras=Count('ventas', filter=VENTAS_VIGENTES),
        total_comprado=Sum('ventas__total', filter=VENTAS_VIGENTES),
        ultima_compra=Max('ventas__fecha', filter=VENTAS_VIGENTES),
    )


@requiere_permiso('clientes.ver')
def panel_clientes(request):
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')
    orden = request.GET.get('orden', '')

    clientes = Cliente.objects.all()
    if q:
        filtro = (Q(nombre__icontains=q) | Q(apellido__icontains=q) | Q(correo__icontains=q) |
                  Q(telefono__icontains=q))
        if q.lstrip('#').isdigit():
            filtro |= Q(pk=int(q.lstrip('#')))
        clientes = clientes.filter(filtro)
    clientes = con_resumen_de_compras(filtrar_estado(clientes, estado))
    orden_sql = {'compras': '-total_comprado', 'puntos': '-puntos_disponibles', 'recientes': '-fecha_registro'}
    clientes = clientes.order_by(orden_sql.get(orden, 'nombre'), 'id')
    pagina, filtros = paginar(request, clientes)

    inicio_mes = timezone.now().date().replace(day=1)
    contexto = {
        'pagina': pagina, 'filtros': filtros, 'q': q, 'estado': estado, 'orden': orden,
        'busqueda': bool(q or estado),
        'kpi': {
            'total': Cliente.objects.count(),
            'activos': Cliente.objects.filter(activo=True).count(),
            'nuevos': Cliente.objects.filter(fecha_registro__date__gte=inicio_mes).count(),
            'ticket': Venta.objects.filter(activo=True, cliente__isnull=False).aggregate(t=Avg('total'))['t'] or 0,
        },
        'puede_editar': tiene_permiso(request, 'clientes.editar'),
        'puede_crear': tiene_permiso(request, 'clientes.crear'),
    }
    return render(request, 'clientes/index.html', contexto)


@requiere_permiso('clientes.ver')
def detalle_cliente(request, pk):
    cliente = get_object_or_404(con_resumen_de_compras(Cliente.objects.all()), pk=pk)
    return render(request, 'clientes/detalle.html', {
        'cliente': cliente,
        'ventas': cliente.ventas.select_related('metodo_pago').order_by('-fecha')[:10],
        'direcciones': cliente.direcciones.filter(activo=True),
        'movimientos_puntos': cliente.movimientos_puntos.select_related('venta')[:10],
        'favoritos': cliente.favoritos.filter(activo=True).count(),
        'puede_editar': tiene_permiso(request, 'clientes.editar'),
    })


@requiere_permiso('clientes.crear')
def crear_cliente(request):
    form = ClienteForm(request.POST or None, crear=True)
    if request.method == 'POST' and form.is_valid():
        cliente = form.save()
        return guardado(request, reverse('clientes'), f'Cliente {cliente} registrado.')
    return mostrar_formulario(request, {
        'form': form, 'titulo': 'Registrar cliente', 'icono': 'fa-user-plus', 'texto_boton': 'Guardar cliente',
        'volver_url': reverse('clientes'),
    })


@requiere_permiso('clientes.editar')
def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    form = ClienteForm(request.POST or None, instance=cliente)
    if not tiene_permiso(request, 'clientes.habilitar'):
        form.fields['activo'].disabled = True

    if request.method == 'POST' and form.is_valid():
        cliente = form.save()
        return guardado(request, reverse('cliente_detalle', args=[cliente.pk]), f'Se guardaron los datos de {cliente}.')

    return mostrar_formulario(request, {
        'form': form, 'titulo': 'Editar cliente', 'icono': 'fa-user-pen', 'subtitulo': f'#{cliente.pk} · {cliente}',
        'volver_url': reverse('cliente_detalle', args=[cliente.pk]),
        'resumen': [('Puntos', cliente.puntos_disponibles),
                    ('Cuenta en línea', 'Sí' if cliente.contrasena_hash else 'No'),
                    ('Cliente desde', cliente.fecha_registro.strftime('%d/%m/%Y'))],
    })
