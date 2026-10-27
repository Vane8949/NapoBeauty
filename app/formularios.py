"""Formularios del panel de administración (ventanas de Agregar y Editar)."""
from decimal import Decimal

from django import forms
from django.contrib.auth.hashers import make_password
from django.db.models import Case, IntegerField, Sum, Value, When

from app.models import (
    Categoria, Cliente, DetalleDevolucion, Devolucion, DevolucionProveedor, Marca, MetodoPago, MovimientoInventario,
    Producto, Proveedor, Rol, Usuario, Venta,
)

CLASE_CAMPO = ('w-full px-4 py-2.5 bg-white border border-gray-200 rounded-lg text-sm '
               'focus:outline-none focus:border-pink-400 focus:ring-2 focus:ring-pink-100')


class EstiloNapo:
    """Aplica el estilo del panel a los campos.

    campos_anchos: campos que ocupan las dos columnas del formulario.
    Las casillas se muestran como interruptor y las imágenes como zona para arrastrar.
    """
    campos_anchos = ()
    mostrar_si = {}

    def aplicar_estilo(self):
        for nombre, campo in self.fields.items():
            widget = campo.widget
            if isinstance(widget, forms.RadioSelect):
                widget.attrs['class'] = 'sr-only peer'
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = 'sr-only peer'
            elif isinstance(widget, forms.FileInput):
                widget.attrs.update({'class': 'sr-only', 'accept': 'image/png,image/jpeg,image/webp'})
            else:
                widget.attrs['class'] = CLASE_CAMPO
            if isinstance(widget, forms.Textarea):
                widget.attrs['rows'] = 3
            campo.ancho = nombre in self.campos_anchos or isinstance(widget, (forms.Textarea, forms.FileInput,
                                                                             forms.RadioSelect))
            # Campos que solo se muestran según otra opción: {'tipo_cliente': 'nuevo'} -> data-mostrar-si
            mostrar = self.mostrar_si.get(nombre)
            if mostrar:
                campo.mostrar_si = f'{mostrar[0]}={mostrar[1]}'


class FormularioNapo(EstiloNapo, forms.ModelForm):
    """Formulario de un modelo. Con crear=True se oculta el interruptor Activo (todo nace habilitado)."""

    def __init__(self, *args, crear=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.crear = crear
        if crear:
            self.fields.pop('activo', None)
        self.aplicar_estilo()


class FormNapo(EstiloNapo, forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilo()


class SelectCategoria(forms.ModelChoiceField):
    def label_from_instance(self, categoria):
        if categoria.categoria_padre_id:
            return f'{categoria.categoria_padre.nombre} › {categoria.nombre}'
        return categoria.nombre


def habilitados_y_actual(modelo, actual_id, orden):
    """Opciones habilitadas, sin perder la que el registro ya tiene aunque esté deshabilitada."""
    consulta = modelo.objects.filter(activo=True)
    if actual_id:
        consulta = consulta | modelo.objects.filter(pk=actual_id)
    return consulta.order_by(*orden)


# -----------------------------------------------------------------------------
# Productos e inventario
# -----------------------------------------------------------------------------

class ProductoForm(FormularioNapo):
    categoria = SelectCategoria(queryset=Categoria.objects.none(), label='Categoría')
    nueva_marca = forms.CharField(label='¿Marca nueva?', max_length=80, required=False,
                                  help_text='Escríbela aquí si no está en la lista.')
    stock = forms.IntegerField(label='Stock', min_value=0, initial=0)
    imagen = forms.ImageField(label='Imagen del producto', required=False, widget=forms.FileInput)

    campos_anchos = ('nombre', 'descripcion', 'imagen')
    field_order = ['nombre', 'sku', 'categoria', 'marca', 'nueva_marca', 'precio_venta', 'precio_compra',
                   'stock', 'stock_minimo', 'proveedor', 'descripcion', 'imagen', 'activo']

    class Meta:
        model = Producto
        fields = ['nombre', 'sku', 'categoria', 'marca', 'precio_venta', 'precio_compra', 'stock_minimo',
                  'proveedor', 'descripcion', 'activo']
        labels = {
            'sku': 'SKU', 'nombre': 'Nombre del producto', 'marca': 'Marca', 'proveedor': 'Proveedor',
            'precio_compra': 'Precio de compra (C$)', 'precio_venta': 'Precio (C$)',
            'stock_minimo': 'Stock mínimo', 'descripcion': 'Descripción', 'activo': 'Activo',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej. Labial líquido Matte'}),
            'sku': forms.TextInput(attrs={'placeholder': 'Ej. NA-001'}),
            'precio_venta': forms.NumberInput(attrs={'placeholder': 'Ej. 180.00', 'step': '0.01'}),
            'precio_compra': forms.NumberInput(attrs={'placeholder': 'Ej. 110.00', 'step': '0.01'}),
        }
        help_texts = {'stock_minimo': 'Por debajo de esta cantidad aparece la alerta de bajo stock.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        actual = self.instance
        self.fields['categoria'].queryset = habilitados_y_actual(
            Categoria, actual.categoria_id, ['categoria_padre__orden', 'categoria_padre__nombre', 'orden']
        ).select_related('categoria_padre')
        self.fields['categoria'].empty_label = 'Selecciona una categoría'
        self.fields['marca'].queryset = habilitados_y_actual(Marca, actual.marca_id, ['nombre'])
        self.fields['marca'].required = False
        self.fields['marca'].empty_label = 'Selecciona una marca'
        self.fields['proveedor'].queryset = habilitados_y_actual(Proveedor, actual.proveedor_id, ['nombre_empresa'])
        self.fields['proveedor'].empty_label = 'Sin proveedor habitual'
        self.fields['stock_minimo'].min_value = 0
        if self.crear:
            self.fields['stock'].label = 'Stock inicial'
            self.fields['stock'].widget.attrs['placeholder'] = 'Ej. 50'
            self.fields['precio_compra'].required = False
        else:
            self.fields['stock'].initial = actual.stock_actual
            self.fields['stock'].help_text = 'Si lo cambias, queda registrado como ajuste en Inventario.'
            self.fields['imagen'].help_text = 'Si subes una imagen nueva, reemplaza a la actual.'

    def clean_precio_compra(self):
        return self.cleaned_data.get('precio_compra') or Decimal('0')

    def clean_imagen(self):
        imagen = self.cleaned_data.get('imagen')
        if imagen and imagen.size > 2 * 1024 * 1024:
            raise forms.ValidationError('La imagen pesa más de 2 MB.')
        return imagen

    def clean(self):
        datos = super().clean()
        compra, venta = datos.get('precio_compra'), datos.get('precio_venta')
        if compra and venta is not None and venta < compra:
            self.add_error('precio_venta', 'El precio de venta es menor que el de compra.')

        nueva = (datos.get('nueva_marca') or '').strip()
        if not datos.get('marca') and not nueva:
            self.add_error('marca', 'Elige una marca o escribe una nueva.')
        elif nueva and not self.errors:
            # La vista guarda todo dentro de una transacción: si algo falla después, la marca no queda creada
            marca = Marca.objects.filter(nombre__iexact=nueva).first() or Marca.objects.create(nombre=nueva)
            datos['marca'] = marca
            self.instance.marca = marca
        return datos


class AjusteInventarioForm(FormNapo):
    """Ajuste de stock: siempre deja un movimiento en el historial.

    Si no se indica el producto (botón "Ajustar Stock" de arriba), se elige en el formulario.
    """

    TIPOS = [
        (MovimientoInventario.Tipo.ENTRADA, 'Entrada (agregar)'),
        (MovimientoInventario.Tipo.SALIDA, 'Salida (restar)'),
        (MovimientoInventario.Tipo.AJUSTE, 'Conteo físico (fijar el stock real)'),
    ]

    producto = forms.ModelChoiceField(label='Producto', queryset=Producto.objects.none(),
                                      empty_label='Selecciona un producto')
    tipo = forms.ChoiceField(label='Tipo de movimiento', choices=TIPOS)
    cantidad = forms.IntegerField(label='Cantidad', min_value=0, widget=forms.NumberInput(attrs={'placeholder': '0'}),
                                  help_text='En "Conteo físico" escribe cuántas unidades contaste en total.')
    stock_minimo = forms.IntegerField(label='Stock mínimo', min_value=0, required=False)
    motivo = forms.CharField(label='Motivo', max_length=200,
                             widget=forms.TextInput(attrs={'placeholder': 'Ej. Reposición, producto dañado, conteo...'}))

    campos_anchos = ('producto', 'motivo')

    def __init__(self, *args, producto=None, **kwargs):
        self.producto = producto
        super().__init__(*args, **kwargs)
        if producto is None:
            self.fields['producto'].queryset = Producto.objects.filter(activo=True).order_by('nombre')
            self.fields['producto'].label_from_instance = (
                lambda p: f'{p.nombre} ({p.sku}) · stock {p.stock_actual}')
            self.fields['stock_minimo'].help_text = 'Déjalo vacío para no cambiarlo.'
        else:
            del self.fields['producto']
            self.fields['stock_minimo'].initial = producto.stock_minimo

    def clean(self):
        datos = super().clean()
        if self.producto is None:
            self.producto = datos.get('producto')
        producto, tipo, cantidad = self.producto, datos.get('tipo'), datos.get('cantidad')
        if producto is None or tipo is None or cantidad is None:
            return datos
        if datos.get('stock_minimo') is None:
            datos['stock_minimo'] = producto.stock_minimo

        actual = producto.stock_actual
        if tipo == MovimientoInventario.Tipo.ENTRADA:
            cambio = cantidad
        elif tipo == MovimientoInventario.Tipo.SALIDA:
            cambio = -cantidad
            if cantidad > actual:
                self.add_error('cantidad', f'Solo hay {actual} unidades en stock.')
        else:
            cambio = cantidad - actual
        if tipo != MovimientoInventario.Tipo.AJUSTE and cantidad == 0:
            self.add_error('cantidad', 'Escribe una cantidad mayor que cero.')
        if cambio == 0 and datos['stock_minimo'] == producto.stock_minimo:
            raise forms.ValidationError('No hay ningún cambio que guardar.')
        datos['cambio'] = cambio
        return datos


# -----------------------------------------------------------------------------
# Ventas
# -----------------------------------------------------------------------------

class SelectProductoVenta(forms.Select):
    """Cada opción lleva su precio y stock para calcular el total en pantalla."""
    campo_precio = 'precio_venta'

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcion = super().create_option(name, value, label, selected, index, subindex, attrs)
        producto = getattr(value, 'instance', None)
        if producto is not None:
            opcion['attrs'].update({'data-precio': str(getattr(producto, self.campo_precio)),
                                    'data-stock': producto.stock_actual})
        return opcion


class SelectProductoCosto(SelectProductoVenta):
    """Igual, pero con el precio de compra (devoluciones a proveedor)."""
    campo_precio = 'precio_compra'


class LineaVentaForm(forms.Form):
    producto = forms.ModelChoiceField(label='Producto', queryset=Producto.objects.none(),
                                      empty_label='Selecciona un producto', widget=SelectProductoVenta)
    cantidad = forms.IntegerField(label='Cantidad', min_value=1, initial=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = Producto.objects.filter(activo=True, stock_actual__gt=0).order_by('nombre')
        self.fields['producto'].label_from_instance = lambda p: f'{p.nombre} · C$ {p.precio_venta:,.2f}'
        self.fields['producto'].widget.attrs['class'] = CLASE_CAMPO
        self.fields['cantidad'].widget.attrs.update({'class': CLASE_CAMPO, 'min': 1})


class LineasVentaBase(forms.BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        cantidades = {}
        for linea in self.forms:
            if not linea.cleaned_data or linea.cleaned_data.get('DELETE'):
                continue
            producto = linea.cleaned_data['producto']
            cantidades[producto] = cantidades.get(producto, 0) + linea.cleaned_data['cantidad']
        if not cantidades:
            raise forms.ValidationError('Agrega al menos un producto.')
        for producto, cantidad in cantidades.items():
            if cantidad > producto.stock_actual:
                raise forms.ValidationError(
                    f'No hay suficiente stock de {producto.nombre}: hay {producto.stock_actual} y pides {cantidad}.')
        self.cantidades = cantidades     # productos repetidos se suman en una sola línea


LineasVenta = forms.formset_factory(LineaVentaForm, formset=LineasVentaBase, extra=0, min_num=1,
                                    validate_min=True, can_delete=True)


class VentaNuevaForm(FormNapo):
    """Registrar venta. El cliente puede ser de mostrador, uno ya registrado o uno nuevo (se registra aquí mismo)."""

    MOSTRADOR, REGISTRADO, NUEVO = 'mostrador', 'registrado', 'nuevo'
    TIPOS_CLIENTE = [(MOSTRADOR, 'Cliente de mostrador'), (REGISTRADO, 'Cliente registrado'), (NUEVO, 'Cliente nuevo')]

    tipo_cliente = forms.ChoiceField(label='Cliente', choices=TIPOS_CLIENTE, initial=MOSTRADOR, widget=forms.RadioSelect,
                                     required=False)
    cliente = forms.ModelChoiceField(label='Buscar cliente registrado', queryset=Cliente.objects.none(), required=False,
                                     empty_label='Selecciona el cliente')
    nuevo_nombre = forms.CharField(label='Nombre', max_length=80, required=False,
                                   widget=forms.TextInput(attrs={'placeholder': 'Ej. María'}))
    nuevo_apellido = forms.CharField(label='Apellido', max_length=80, required=False,
                                     widget=forms.TextInput(attrs={'placeholder': 'Ej. López'}))
    nuevo_telefono = forms.CharField(label='Teléfono', max_length=20, required=False,
                                     widget=forms.TextInput(attrs={'placeholder': '+505 8888-8888'}))
    nuevo_correo = forms.EmailField(label='Correo electrónico', max_length=150, required=False,
                                    widget=forms.EmailInput(attrs={'placeholder': 'cliente@email.com'}),
                                    help_text='Escribe al menos el teléfono o el correo.')
    metodo_pago = forms.ModelChoiceField(label='Método de pago', queryset=MetodoPago.objects.none(),
                                         empty_label=None)
    estado = forms.ChoiceField(label='Estado', choices=Venta.Estado.choices, initial=Venta.Estado.ENTREGADO)
    descuento = forms.DecimalField(label='Descuento (C$)', min_value=0, max_digits=12, decimal_places=2,
                                   required=False, widget=forms.NumberInput(attrs={'placeholder': '0.00', 'step': '0.01'}))
    notas = forms.CharField(label='Notas', required=False, max_length=300, widget=forms.Textarea)

    campos_anchos = ('cliente',)
    mostrar_si = {
        'cliente': ('tipo_cliente', REGISTRADO),
        'nuevo_nombre': ('tipo_cliente', NUEVO), 'nuevo_apellido': ('tipo_cliente', NUEVO),
        'nuevo_telefono': ('tipo_cliente', NUEVO), 'nuevo_correo': ('tipo_cliente', NUEVO),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].queryset = Cliente.objects.filter(activo=True).order_by('nombre', 'apellido')
        self.fields['cliente'].label_from_instance = (
            lambda c: f'{c} · {c.telefono or c.correo or "sin contacto"}')
        self.fields['metodo_pago'].queryset = MetodoPago.objects.filter(activo=True).order_by('nombre')
        for campo in ('cliente', 'nuevo_nombre'):
            self.fields[campo].obligatorio_si = True     # muestra el * aunque el campo sea opcional para Django

    def clean_descuento(self):
        return self.cleaned_data.get('descuento') or Decimal('0')

    def clean(self):
        datos = super().clean()
        tipo = datos.get('tipo_cliente') or (self.REGISTRADO if datos.get('cliente') else self.MOSTRADOR)
        datos['tipo_cliente'] = tipo
        if tipo == self.REGISTRADO and not datos.get('cliente'):
            self.add_error('cliente', 'Elige el cliente registrado.')
        if tipo != self.REGISTRADO:
            datos['cliente'] = None
        if tipo == self.NUEVO:
            nombre = (datos.get('nuevo_nombre') or '').strip()
            telefono = (datos.get('nuevo_telefono') or '').strip()
            correo = (datos.get('nuevo_correo') or '').strip().lower()
            if not nombre:
                self.add_error('nuevo_nombre', 'Escribe el nombre del cliente.')
            if not telefono and not correo and 'nuevo_correo' not in self.errors:
                self.add_error('nuevo_telefono', 'Escribe el teléfono o el correo del cliente.')
            if correo and Cliente.objects.filter(correo__iexact=correo).exists():
                self.add_error('nuevo_correo', 'Ya hay un cliente con este correo: elígelo en "Cliente registrado".')
            if telefono and Cliente.objects.filter(telefono=telefono, activo=True).exists():
                self.add_error('nuevo_telefono', 'Ya hay un cliente con este teléfono: elígelo en "Cliente registrado".')
            datos['datos_cliente_nuevo'] = {'nombre': nombre, 'apellido': (datos.get('nuevo_apellido') or '').strip() or None,
                                            'telefono': telefono or None, 'correo': correo or None}
        return datos


class VentaForm(FormularioNapo):
    campos_anchos = ('notas',)

    class Meta:
        model = Venta
        fields = ['estado', 'metodo_pago', 'notas', 'activo']
        labels = {'estado': 'Estado de la venta', 'metodo_pago': 'Método de pago', 'notas': 'Notas',
                  'activo': 'Venta vigente'}
        help_texts = {'activo': 'Si la apagas, la venta queda anulada: los productos vuelven al inventario '
                                'y se le quitan al cliente los puntos ganados.'}
        widgets = {'notas': forms.Textarea}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['metodo_pago'].queryset = habilitados_y_actual(
            MetodoPago, self.instance.metodo_pago_id, ['nombre'])
        self.fields['metodo_pago'].empty_label = None


# -----------------------------------------------------------------------------
# Devoluciones
# -----------------------------------------------------------------------------

def cantidad_ya_devuelta(detalle_venta):
    """Unidades de una línea de venta que ya están en otras devoluciones vigentes."""
    return DetalleDevolucion.objects.filter(
        detalle_venta=detalle_venta, devolucion__activo=True,
    ).exclude(devolucion__estado=Devolucion.Estado.RECHAZADA).aggregate(t=Sum('cantidad'))['t'] or 0


class DevolucionNuevaForm(FormNapo):
    """Registrar devolución. Al elegir la venta se recarga el formulario con sus productos."""

    venta = forms.ModelChoiceField(label='Venta original', queryset=Venta.objects.none(),
                                   empty_label='Selecciona la venta')
    motivo = forms.ChoiceField(label='Motivo de devolución', choices=Devolucion.Motivo.choices)
    tipo_resolucion = forms.ChoiceField(label='Resolución', choices=Devolucion.TipoResolucion.choices)
    monto_reembolso = forms.DecimalField(
        label='Monto a reembolsar (C$)', min_value=0, max_digits=12, decimal_places=2, required=False,
        help_text='Si lo dejas vacío y la resolución es Reembolso, se calcula con los precios pagados.')
    descripcion = forms.CharField(label='Descripción', required=False, max_length=500, widget=forms.Textarea)

    campos_anchos = ('venta',)

    def __init__(self, *args, venta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['venta'].queryset = (Venta.objects.filter(activo=True).select_related('cliente')
                                         .order_by('-fecha', '-id'))
        self.fields['venta'].label_from_instance = lambda v: (
            f'{v.numero_factura} · {v.cliente or "Cliente de mostrador"} · {v.fecha:%d/%m/%Y} · C$ {v.total:,.2f}')
        self.venta = venta
        self.lineas = []
        if venta is None:
            return
        self.fields['venta'].initial = venta.pk
        for detalle in venta.detalles.select_related('producto__proveedor'):
            disponible = detalle.cantidad - cantidad_ya_devuelta(detalle)
            cantidad = forms.IntegerField(min_value=0, max_value=max(disponible, 0), initial=0, required=False,
                                          widget=forms.NumberInput(attrs={'class': CLASE_CAMPO, 'min': 0,
                                                                          'max': max(disponible, 0)}))
            # El producto se puede devolver al proveedor solo si tiene uno asignado
            proveedor = detalle.producto.proveedor
            opciones = [(valor, texto) for valor, texto in DetalleDevolucion.Destino.choices
                        if valor != DetalleDevolucion.Destino.PROVEEDOR or proveedor]
            if proveedor:
                opciones = [(v, f'{t} ({proveedor.nombre_empresa})' if v == DetalleDevolucion.Destino.PROVEEDOR else t)
                            for v, t in opciones]
            destino = forms.ChoiceField(choices=opciones, initial=DetalleDevolucion.Destino.INVENTARIO, required=False,
                                        widget=forms.Select(attrs={'class': CLASE_CAMPO}))
            self.fields[f'cantidad_{detalle.pk}'] = cantidad
            self.fields[f'destino_{detalle.pk}'] = destino
            cantidad.oculto_en_lista = destino.oculto_en_lista = True
            self.lineas.append({'detalle': detalle, 'disponible': disponible, 'devueltos': detalle.cantidad - disponible,
                                'cantidad': self[f'cantidad_{detalle.pk}'], 'destino': self[f'destino_{detalle.pk}']})

    def clean(self):
        datos = super().clean()
        venta = datos.get('venta')
        if venta is None:
            return datos
        if self.venta is None or venta.pk != self.venta.pk:
            raise forms.ValidationError('Elige la venta y luego indica qué productos se devuelven.')
        elegidas = []
        for linea in self.lineas:
            cantidad = datos.get(f'cantidad_{linea["detalle"].pk}') or 0
            if cantidad:
                destino = datos.get(f'destino_{linea["detalle"].pk}') or DetalleDevolucion.Destino.INVENTARIO
                elegidas.append((linea['detalle'], cantidad, destino))
        if not elegidas:
            raise forms.ValidationError('Indica la cantidad de al menos un producto devuelto.')
        monto = datos.get('monto_reembolso')
        if monto is None:
            monto = (sum(d.precio_unitario * c for d, c, _ in elegidas)
                     if datos.get('tipo_resolucion') == Devolucion.TipoResolucion.REEMBOLSO else Decimal('0'))
        if monto > venta.total:
            self.add_error('monto_reembolso', f'No puede ser mayor que el total de la venta (C$ {venta.total:,.2f}).')
        datos['monto_reembolso'] = monto
        datos['elegidas'] = elegidas
        return datos


class DevolucionForm(FormularioNapo):
    campos_anchos = ('descripcion',)

    class Meta:
        model = Devolucion
        fields = ['estado', 'tipo_resolucion', 'motivo', 'monto_reembolso', 'descripcion', 'activo']
        labels = {'estado': 'Estado', 'tipo_resolucion': 'Resolución', 'motivo': 'Motivo',
                  'monto_reembolso': 'Monto a reembolsar (C$)', 'descripcion': 'Descripción',
                  'activo': 'Devolución vigente'}
        help_texts = {'estado': 'Al marcarla como Completada, los productos que regresan al stock se suman al '
                                'inventario y los que van al proveedor pasan a "Devoluciones a proveedores". '
                                'Después ya no se puede cambiar el estado.'}
        widgets = {'descripcion': forms.Textarea}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.estado == Devolucion.Estado.COMPLETADA:
            self.fields['estado'].disabled = True

    def clean_monto_reembolso(self):
        monto = self.cleaned_data['monto_reembolso']
        total_venta = self.instance.venta.total
        if monto is not None and total_venta is not None and monto > total_venta:
            raise forms.ValidationError(f'No puede ser mayor que el total de la venta (C$ {total_venta:,.2f}).')
        return monto


class LineaDevProveedorForm(forms.Form):
    """Un producto que se le devuelve al proveedor. Primero salen los productos de ese proveedor."""

    producto = forms.ModelChoiceField(label='Producto', queryset=Producto.objects.none(),
                                      empty_label='Selecciona un producto', widget=SelectProductoCosto)
    cantidad = forms.IntegerField(label='Cantidad', min_value=1, initial=1)

    def __init__(self, *args, proveedor=None, **kwargs):
        super().__init__(*args, **kwargs)
        consulta = Producto.objects.filter(activo=True, stock_actual__gt=0)
        if proveedor is not None:
            consulta = consulta.annotate(otro=Case(When(proveedor_id=proveedor.pk, then=Value(0)), default=Value(1),
                                                   output_field=IntegerField())).order_by('otro', 'nombre')
            self.fields['producto'].label_from_instance = lambda p: (
                f'{p.nombre} · stock {p.stock_actual}' + ('' if p.proveedor_id == proveedor.pk else ' · otro proveedor'))
        else:
            consulta = consulta.order_by('nombre')
            self.fields['producto'].label_from_instance = lambda p: f'{p.nombre} · stock {p.stock_actual}'
        self.fields['producto'].queryset = consulta
        self.fields['producto'].widget.attrs['class'] = CLASE_CAMPO
        self.fields['cantidad'].widget.attrs.update({'class': CLASE_CAMPO, 'min': 1})


LineasDevProveedor = forms.formset_factory(LineaDevProveedorForm, formset=LineasVentaBase, extra=0, min_num=1,
                                           validate_min=True, can_delete=True)


class DevolucionProveedorNuevaForm(FormNapo):
    """Devolver al proveedor productos que están en el inventario (defectuosos, vencidos...)."""

    proveedor = forms.ModelChoiceField(label='Proveedor', queryset=Proveedor.objects.none(),
                                       empty_label='Selecciona el proveedor')
    motivo = forms.ChoiceField(label='Motivo', choices=DevolucionProveedor.Motivo.choices)
    resolucion = forms.ChoiceField(label='¿Qué se espera del proveedor?', choices=DevolucionProveedor.Resolucion.choices)
    factura_proveedor = forms.CharField(label='Factura del proveedor', max_length=30, required=False,
                                        widget=forms.TextInput(attrs={'placeholder': 'Opcional. Ej. F-00123'}))
    descripcion = forms.CharField(label='Descripción', required=False, max_length=500, widget=forms.Textarea)

    campos_anchos = ('proveedor',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proveedor'].queryset = Proveedor.objects.filter(activo=True).order_by('nombre_empresa')


class DevolucionProveedorForm(FormularioNapo):
    campos_anchos = ('descripcion',)

    class Meta:
        model = DevolucionProveedor
        fields = ['estado', 'resolucion', 'monto_credito', 'factura_proveedor', 'motivo', 'descripcion', 'activo']
        labels = {'estado': 'Estado', 'resolucion': 'Resolución', 'monto_credito': 'Monto acreditado (C$)',
                  'factura_proveedor': 'Factura del proveedor', 'motivo': 'Motivo', 'descripcion': 'Descripción',
                  'activo': 'Devolución vigente'}
        help_texts = {
            'estado': 'Completada con Reposición suma al stock las unidades que manda el proveedor. '
                      'Rechazada deja los productos dados de baja. Después ya no se puede cambiar.',
            'monto_credito': 'Valor de la nota de crédito o del reembolso que dio el proveedor.',
            'activo': 'Solo mientras está Pendiente. Si la apagas, lo que salió del inventario regresa al stock.',
        }
        widgets = {'descripcion': forms.Textarea}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.cerrada:
            self.fields['estado'].disabled = True
            self.fields['resolucion'].disabled = True
        if self.instance.estado != DevolucionProveedor.Estado.PENDIENTE:
            self.fields['activo'].disabled = True

    def clean_factura_proveedor(self):
        return self.cleaned_data.get('factura_proveedor') or None


# -----------------------------------------------------------------------------
# Clientes, proveedores y usuarios
# -----------------------------------------------------------------------------

class ClienteForm(FormularioNapo):
    class Meta:
        model = Cliente
        fields = ['nombre', 'apellido', 'correo', 'telefono', 'fecha_nacimiento', 'activo']
        labels = {'nombre': 'Nombre', 'apellido': 'Apellido', 'correo': 'Correo electrónico',
                  'telefono': 'Teléfono', 'fecha_nacimiento': 'Fecha de nacimiento', 'activo': 'Activo'}
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'telefono': forms.TextInput(attrs={'placeholder': '+505 8888-8888'}),
            'correo': forms.EmailInput(attrs={'placeholder': 'cliente@email.com'}),
        }

    def clean_correo(self):
        correo = self.cleaned_data.get('correo') or None
        if correo is None and self.instance.contrasena_hash:
            raise forms.ValidationError('Este cliente tiene cuenta en la tienda en línea: el correo es obligatorio.')
        return correo


class ProveedorForm(FormularioNapo):
    campos_anchos = ('nombre_empresa', 'direccion')

    class Meta:
        model = Proveedor
        fields = ['nombre_empresa', 'ruc', 'nombre_contacto', 'telefono', 'correo', 'direccion', 'activo']
        labels = {'nombre_empresa': 'Empresa', 'ruc': 'RUC', 'nombre_contacto': 'Persona de contacto',
                  'telefono': 'Teléfono', 'correo': 'Correo electrónico', 'direccion': 'Dirección',
                  'activo': 'Activo'}
        widgets = {'nombre_empresa': forms.TextInput(attrs={'placeholder': 'Ej. Distribuidora Belleza Total'}),
                   'ruc': forms.TextInput(attrs={'placeholder': 'Ej. J0310000012345'})}

    def clean_ruc(self):
        return self.cleaned_data.get('ruc') or None


class UsuarioForm(FormularioNapo):
    nueva_contrasena = forms.CharField(
        label='Nueva contraseña', required=False, min_length=8, strip=False,
        widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'}),
        help_text='Déjala en blanco para no cambiarla. Mínimo 8 caracteres.')
    confirmar_contrasena = forms.CharField(
        label='Confirmar contraseña', required=False, strip=False,
        widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'}))

    class Meta:
        model = Usuario
        fields = ['nombre', 'apellido', 'nombre_usuario', 'correo', 'telefono', 'rol', 'activo']
        labels = {'nombre': 'Nombre', 'apellido': 'Apellido', 'nombre_usuario': 'Nombre de usuario',
                  'correo': 'Correo electrónico', 'telefono': 'Teléfono', 'rol': 'Rol', 'activo': 'Activo'}
        help_texts = {'activo': 'Un usuario deshabilitado no puede entrar al sistema.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rol'].queryset = habilitados_y_actual(Rol, self.instance.rol_id, ['nombre'])
        self.fields['rol'].empty_label = 'Selecciona un rol'
        if self.crear:
            self.fields['nueva_contrasena'].label = 'Contraseña'
            self.fields['nueva_contrasena'].required = True
            self.fields['nueva_contrasena'].help_text = 'Mínimo 8 caracteres.'
            self.fields['confirmar_contrasena'].required = True

    def clean(self):
        datos = super().clean()
        nueva, confirmar = datos.get('nueva_contrasena'), datos.get('confirmar_contrasena')
        if nueva and nueva != confirmar:
            self.add_error('confirmar_contrasena', 'Las contraseñas no coinciden.')

        # Siempre debe quedar al menos un Administrador habilitado
        if self.instance.pk:
            rol, activo = datos.get('rol'), datos.get('activo', self.instance.activo)
            era_admin = self.instance.activo and self.instance.rol.nombre == 'Administrador'
            sigue_admin = bool(activo) and rol is not None and rol.nombre == 'Administrador'
            if era_admin and not sigue_admin:
                otros = Usuario.objects.filter(activo=True, rol__nombre='Administrador').exclude(pk=self.instance.pk)
                if not otros.exists():
                    raise forms.ValidationError(
                        'Este es el único administrador habilitado. Habilita o nombra otro administrador primero.')
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.cleaned_data.get('nueva_contrasena'):
            usuario.contrasena_hash = make_password(self.cleaned_data['nueva_contrasena'])
        if commit:
            usuario.save()
        return usuario
