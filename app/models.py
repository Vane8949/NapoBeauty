"""Modelos de Napo Beauty.

Corresponden a las tablas que crea database/napobeauty_sqlserver.sql en SQL Server.
Todas usan managed = False: la estructura la controla ese script, no las migraciones
de Django. Si se cambia una tabla, primero se cambia el script y luego el modelo.

Reglas del negocio que se respetan aquí:
  - Nada se borra: .delete() lanza BorradoNoPermitido. Para "quitar" algo se usa
    .deshabilitar() (pone Activo = 0) y .habilitar() para volver a mostrarlo.
  - Model.objects.activos() devuelve solo los registros habilitados.
"""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F
from django.utils import timezone


# =============================================================================
# Base: sin borrado, con habilitar / deshabilitar
# =============================================================================

class BorradoNoPermitido(Exception):
    """En Napo Beauty no se borran registros; se deshabilitan."""


class SinBorradoQuerySet(models.QuerySet):
    def delete(self):
        raise BorradoNoPermitido('No se permite borrar. Use .deshabilitar().')

    def activos(self):
        return self.filter(activo=True)

    def inactivos(self):
        return self.filter(activo=False)

    def habilitar(self):
        return self.update(activo=True)

    def deshabilitar(self):
        return self.update(activo=False)


class ModeloNapo(models.Model):
    """Base de todos los modelos: bloquea el borrado."""

    objects = SinBorradoQuerySet.as_manager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        raise BorradoNoPermitido(f'No se permite borrar {self._meta.verbose_name}. Use .deshabilitar().')


class ModeloConActivo(ModeloNapo):
    """Base de las tablas que tienen la columna Activo."""

    activo = models.BooleanField(default=True, db_column='Activo')

    class Meta:
        abstract = True

    def habilitar(self):
        self.activo = True
        self.save(update_fields=['activo'])

    def deshabilitar(self):
        self.activo = False
        self.save(update_fields=['activo'])


def dinero(digitos=10, **kwargs):
    """Monto en córdobas: DECIMAL(digitos, 2)."""
    return models.DecimalField(max_digits=digitos, decimal_places=2, **kwargs)


# =============================================================================
# 1. Seguridad: roles, permisos y usuarios
# =============================================================================

class Rol(ModeloConActivo):
    id = models.AutoField(primary_key=True, db_column='RolId')
    nombre = models.CharField(max_length=50, unique=True, db_column='Nombre')
    descripcion = models.CharField(max_length=200, null=True, blank=True, db_column='Descripcion')

    class Meta:
        managed = False
        db_table = 'Rol'
        verbose_name = 'rol'
        verbose_name_plural = 'roles'

    def __str__(self):
        return self.nombre


class Usuario(ModeloConActivo):
    id = models.AutoField(primary_key=True, db_column='UsuarioId')
    rol = models.ForeignKey(Rol, models.PROTECT, db_column='RolId', related_name='usuarios')
    nombre = models.CharField(max_length=80, db_column='Nombre')
    apellido = models.CharField(max_length=80, db_column='Apellido')
    nombre_usuario = models.CharField(max_length=50, unique=True, db_column='NombreUsuario')
    correo = models.EmailField(max_length=150, unique=True, db_column='Correo')
    telefono = models.CharField(max_length=20, null=True, blank=True, db_column='Telefono')
    contrasena_hash = models.CharField(max_length=255, db_column='ContrasenaHash')
    foto_ruta = models.CharField(max_length=255, null=True, blank=True, db_column='FotoRuta')
    ultimo_acceso = models.DateTimeField(null=True, blank=True, db_column='UltimoAcceso')
    fecha_creacion = models.DateTimeField(default=timezone.now, db_column='FechaCreacion')

    class Meta:
        managed = False
        db_table = 'Usuario'
        verbose_name = 'usuario'

    def __str__(self):
        return f'{self.nombre} {self.apellido}'

    def tiene_permiso(self, codigo):
        """Ej.: usuario.tiene_permiso('productos.crear')"""
        return self.activo and RolPermiso.objects.filter(
            rol_id=self.rol_id, rol__activo=True, activo=True,
            permiso__codigo=codigo, permiso__activo=True,
        ).exists()


class Permiso(ModeloConActivo):
    class Accion(models.TextChoices):
        VER = 'ver', 'Ver'
        CREAR = 'crear', 'Crear'
        EDITAR = 'editar', 'Editar'
        HABILITAR = 'habilitar', 'Habilitar o deshabilitar'
        EXPORTAR = 'exportar', 'Exportar'

    id = models.AutoField(primary_key=True, db_column='PermisoId')
    codigo = models.CharField(max_length=60, unique=True, db_column='Codigo')
    modulo = models.CharField(max_length=40, db_column='Modulo')
    accion = models.CharField(max_length=20, choices=Accion.choices, db_column='Accion')
    descripcion = models.CharField(max_length=200, null=True, blank=True, db_column='Descripcion')

    class Meta:
        managed = False
        db_table = 'Permiso'
        verbose_name = 'permiso'

    def __str__(self):
        return self.codigo


class RolPermiso(ModeloConActivo):
    pk = models.CompositePrimaryKey('rol_id', 'permiso_id')
    rol = models.ForeignKey(Rol, models.PROTECT, db_column='RolId', related_name='permisos_asignados')
    permiso = models.ForeignKey(Permiso, models.PROTECT, db_column='PermisoId', related_name='roles_asignados')
    fecha_asignacion = models.DateTimeField(default=timezone.now, db_column='FechaAsignacion')

    class Meta:
        managed = False
        db_table = 'RolPermiso'
        verbose_name = 'permiso del rol'
        verbose_name_plural = 'permisos de los roles'


# =============================================================================
# 2. Catálogo
# =============================================================================

class Categoria(ModeloConActivo):
    id = models.AutoField(primary_key=True, db_column='CategoriaId')
    categoria_padre = models.ForeignKey('self', models.PROTECT, null=True, blank=True,
                                        db_column='CategoriaPadreId', related_name='subcategorias')
    nombre = models.CharField(max_length=80, db_column='Nombre')
    icono = models.CharField(max_length=50, null=True, blank=True, db_column='Icono')
    orden = models.IntegerField(default=0, db_column='Orden')

    class Meta:
        managed = False
        db_table = 'Categoria'
        verbose_name = 'categoría'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class Marca(ModeloConActivo):
    id = models.AutoField(primary_key=True, db_column='MarcaId')
    nombre = models.CharField(max_length=80, unique=True, db_column='Nombre')

    class Meta:
        managed = False
        db_table = 'Marca'
        verbose_name = 'marca'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Proveedor(ModeloConActivo):
    id = models.AutoField(primary_key=True, db_column='ProveedorId')
    nombre_empresa = models.CharField(max_length=150, db_column='NombreEmpresa')
    nombre_contacto = models.CharField(max_length=120, null=True, blank=True, db_column='NombreContacto')
    ruc = models.CharField(max_length=20, null=True, blank=True, unique=True, db_column='RUC')
    telefono = models.CharField(max_length=20, null=True, blank=True, db_column='Telefono')
    correo = models.EmailField(max_length=150, null=True, blank=True, db_column='Correo')
    direccion = models.CharField(max_length=300, null=True, blank=True, db_column='Direccion')
    fecha_registro = models.DateTimeField(default=timezone.now, db_column='FechaRegistro')

    class Meta:
        managed = False
        db_table = 'Proveedor'
        verbose_name = 'proveedor'
        verbose_name_plural = 'proveedores'

    def __str__(self):
        return self.nombre_empresa


class Producto(ModeloConActivo):
    id = models.AutoField(primary_key=True, db_column='ProductoId')
    sku = models.CharField(max_length=30, unique=True, db_column='SKU')
    nombre = models.CharField(max_length=150, db_column='Nombre')
    descripcion = models.TextField(null=True, blank=True, db_column='Descripcion')
    categoria = models.ForeignKey(Categoria, models.PROTECT, db_column='CategoriaId', related_name='productos')
    marca = models.ForeignKey(Marca, models.PROTECT, db_column='MarcaId', related_name='productos')
    proveedor = models.ForeignKey(Proveedor, models.PROTECT, null=True, blank=True,
                                  db_column='ProveedorId', related_name='productos')
    precio_compra = dinero(default=0, validators=[MinValueValidator(0)], db_column='PrecioCompra')
    precio_venta = dinero(validators=[MinValueValidator(0)], db_column='PrecioVenta')
    stock_actual = models.IntegerField(default=0, validators=[MinValueValidator(0)], db_column='StockActual')
    stock_minimo = models.IntegerField(default=5, validators=[MinValueValidator(0)], db_column='StockMinimo')
    fecha_creacion = models.DateTimeField(default=timezone.now, db_column='FechaCreacion')

    class Meta:
        managed = False
        db_table = 'Producto'
        verbose_name = 'producto'

    def __str__(self):
        return f'{self.marca} {self.nombre}' if self.marca_id else self.nombre

    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo


class ProductoImagen(ModeloConActivo):
    id = models.AutoField(primary_key=True, db_column='ProductoImagenId')
    producto = models.ForeignKey(Producto, models.PROTECT, db_column='ProductoId', related_name='imagenes')
    ruta = models.ImageField(upload_to='productos/', max_length=255, db_column='Ruta')
    es_principal = models.BooleanField(default=False, db_column='EsPrincipal')
    orden = models.IntegerField(default=0, db_column='Orden')

    class Meta:
        managed = False
        db_table = 'ProductoImagen'
        verbose_name = 'imagen de producto'
        verbose_name_plural = 'imágenes de productos'
        ordering = ['-es_principal', 'orden']


# =============================================================================
# 3. Compras e inventario
# =============================================================================

class Compra(ModeloConActivo):
    class Estado(models.TextChoices):
        PENDIENTE = 'Pendiente'
        RECIBIDA = 'Recibida'

    id = models.AutoField(primary_key=True, db_column='CompraId')
    proveedor = models.ForeignKey(Proveedor, models.PROTECT, db_column='ProveedorId', related_name='compras')
    usuario = models.ForeignKey(Usuario, models.PROTECT, db_column='UsuarioId', related_name='compras')
    numero_factura = models.CharField(max_length=30, null=True, blank=True, db_column='NumeroFactura')
    fecha = models.DateTimeField(default=timezone.now, db_column='Fecha')
    total = dinero(12, default=0, db_column='Total')
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.RECIBIDA, db_column='Estado')
    observaciones = models.CharField(max_length=300, null=True, blank=True, db_column='Observaciones')

    class Meta:
        managed = False
        db_table = 'Compra'
        verbose_name = 'compra'


class DetalleCompra(ModeloNapo):
    id = models.AutoField(primary_key=True, db_column='DetalleCompraId')
    compra = models.ForeignKey(Compra, models.PROTECT, db_column='CompraId', related_name='detalles')
    producto = models.ForeignKey(Producto, models.PROTECT, db_column='ProductoId', related_name='detalles_compra')
    cantidad = models.IntegerField(validators=[MinValueValidator(1)], db_column='Cantidad')
    costo_unitario = dinero(validators=[MinValueValidator(0)], db_column='CostoUnitario')
    # Columna calculada en SQL Server: no se escribe, solo se lee
    subtotal = models.GeneratedField(
        expression=F('cantidad') * F('costo_unitario'),
        output_field=models.DecimalField(max_digits=21, decimal_places=2),
        db_persist=True, db_column='Subtotal',
    )

    class Meta:
        managed = False
        db_table = 'DetalleCompra'
        verbose_name = 'detalle de compra'


class MovimientoInventario(ModeloNapo):
    """Historial inmutable de cambios de stock."""

    class Tipo(models.TextChoices):
        ENTRADA = 'Entrada'
        SALIDA = 'Salida'
        AJUSTE = 'Ajuste'
        DEVOLUCION = 'Devolucion', 'Devolución'

    id = models.AutoField(primary_key=True, db_column='MovimientoInventarioId')
    producto = models.ForeignKey(Producto, models.PROTECT, db_column='ProductoId', related_name='movimientos')
    usuario = models.ForeignKey(Usuario, models.PROTECT, null=True, blank=True, db_column='UsuarioId',
                                related_name='movimientos_inventario')
    tipo = models.CharField(max_length=20, choices=Tipo.choices, db_column='Tipo')
    cantidad = models.IntegerField(db_column='Cantidad')            # positiva entra, negativa sale
    stock_anterior = models.IntegerField(db_column='StockAnterior')
    stock_nuevo = models.IntegerField(db_column='StockNuevo')
    motivo = models.CharField(max_length=200, null=True, blank=True, db_column='Motivo')
    tipo_referencia = models.CharField(max_length=20, null=True, blank=True, db_column='TipoReferencia')
    referencia_id = models.IntegerField(null=True, blank=True, db_column='ReferenciaId')
    fecha = models.DateTimeField(default=timezone.now, db_column='Fecha')

    class Meta:
        managed = False
        db_table = 'MovimientoInventario'
        verbose_name = 'movimiento de inventario'
        verbose_name_plural = 'movimientos de inventario'
        ordering = ['-fecha']


# =============================================================================
# 4. Clientes y vista cliente
# =============================================================================

class Cliente(ModeloConActivo):
    id = models.AutoField(primary_key=True, db_column='ClienteId')
    nombre = models.CharField(max_length=80, db_column='Nombre')
    apellido = models.CharField(max_length=80, null=True, blank=True, db_column='Apellido')
    correo = models.EmailField(max_length=150, null=True, blank=True, unique=True, db_column='Correo')
    telefono = models.CharField(max_length=20, null=True, blank=True, db_column='Telefono')
    contrasena_hash = models.CharField(max_length=255, null=True, blank=True, db_column='ContrasenaHash')
    fecha_nacimiento = models.DateField(null=True, blank=True, db_column='FechaNacimiento')
    puntos_disponibles = models.IntegerField(default=0, validators=[MinValueValidator(0)],
                                             db_column='PuntosDisponibles')
    fecha_registro = models.DateTimeField(default=timezone.now, db_column='FechaRegistro')

    class Meta:
        managed = False
        db_table = 'Cliente'
        verbose_name = 'cliente'

    def __str__(self):
        return f'{self.nombre} {self.apellido or ""}'.strip()


class DireccionCliente(ModeloConActivo):
    id = models.AutoField(primary_key=True, db_column='DireccionClienteId')
    cliente = models.ForeignKey(Cliente, models.PROTECT, db_column='ClienteId', related_name='direcciones')
    alias = models.CharField(max_length=50, db_column='Alias')
    nombre_recibe = models.CharField(max_length=120, db_column='NombreRecibe')
    telefono = models.CharField(max_length=20, db_column='Telefono')
    departamento = models.CharField(max_length=60, db_column='Departamento')
    municipio = models.CharField(max_length=60, db_column='Municipio')
    direccion_exacta = models.CharField(max_length=300, db_column='DireccionExacta')
    punto_referencia = models.CharField(max_length=200, null=True, blank=True, db_column='PuntoReferencia')
    es_predeterminada = models.BooleanField(default=False, db_column='EsPredeterminada')

    class Meta:
        managed = False
        db_table = 'DireccionCliente'
        verbose_name = 'dirección de cliente'
        verbose_name_plural = 'direcciones de clientes'

    def __str__(self):
        return f'{self.alias}: {self.direccion_exacta}, {self.municipio}'


class MetodoPagoCliente(ModeloConActivo):
    """Solo token de la pasarela y últimos 4 dígitos: nunca el número completo ni el CVV."""

    class Tipo(models.TextChoices):
        TARJETA = 'Tarjeta'
        TRANSFERENCIA = 'Transferencia'
        BILLETERA = 'Billetera'

    id = models.AutoField(primary_key=True, db_column='MetodoPagoClienteId')
    cliente = models.ForeignKey(Cliente, models.PROTECT, db_column='ClienteId', related_name='metodos_pago')
    tipo = models.CharField(max_length=20, choices=Tipo.choices, db_column='Tipo')
    marca_tarjeta = models.CharField(max_length=20, null=True, blank=True, db_column='MarcaTarjeta')
    ultimos_digitos = models.CharField(max_length=4, null=True, blank=True, db_column='UltimosDigitos')
    mes_vencimiento = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(12)], db_column='MesVencimiento')
    anio_vencimiento = models.SmallIntegerField(null=True, blank=True, db_column='AnioVencimiento')
    token_pasarela = models.CharField(max_length=255, null=True, blank=True, db_column='TokenPasarela')
    es_predeterminado = models.BooleanField(default=False, db_column='EsPredeterminado')

    class Meta:
        managed = False
        db_table = 'MetodoPagoCliente'
        verbose_name = 'método de pago del cliente'
        verbose_name_plural = 'métodos de pago de clientes'


class Favorito(ModeloConActivo):
    pk = models.CompositePrimaryKey('cliente_id', 'producto_id')
    cliente = models.ForeignKey(Cliente, models.PROTECT, db_column='ClienteId', related_name='favoritos')
    producto = models.ForeignKey(Producto, models.PROTECT, db_column='ProductoId', related_name='favorito_de')
    fecha_agregado = models.DateTimeField(default=timezone.now, db_column='FechaAgregado')

    class Meta:
        managed = False
        db_table = 'Favorito'
        verbose_name = 'favorito'


class ListaDeseo(ModeloConActivo):
    pk = models.CompositePrimaryKey('cliente_id', 'producto_id')
    cliente = models.ForeignKey(Cliente, models.PROTECT, db_column='ClienteId', related_name='lista_deseos')
    producto = models.ForeignKey(Producto, models.PROTECT, db_column='ProductoId', related_name='deseado_por')
    fecha_agregado = models.DateTimeField(default=timezone.now, db_column='FechaAgregado')
    avisar_disponible = models.BooleanField(default=False, db_column='AvisarDisponible')

    class Meta:
        managed = False
        db_table = 'ListaDeseo'
        verbose_name = 'producto en lista de deseos'
        verbose_name_plural = 'lista de deseos'


class CarritoItem(ModeloConActivo):
    pk = models.CompositePrimaryKey('cliente_id', 'producto_id')
    cliente = models.ForeignKey(Cliente, models.PROTECT, db_column='ClienteId', related_name='carrito')
    producto = models.ForeignKey(Producto, models.PROTECT, db_column='ProductoId', related_name='en_carritos')
    cantidad = models.IntegerField(default=1, validators=[MinValueValidator(1)], db_column='Cantidad')
    fecha_agregado = models.DateTimeField(default=timezone.now, db_column='FechaAgregado')

    class Meta:
        managed = False
        db_table = 'CarritoItem'
        verbose_name = 'producto en el carrito'
        verbose_name_plural = 'carrito'


class Resena(ModeloConActivo):
    id = models.AutoField(primary_key=True, db_column='ResenaId')
    producto = models.ForeignKey(Producto, models.PROTECT, db_column='ProductoId', related_name='resenas')
    cliente = models.ForeignKey(Cliente, models.PROTECT, db_column='ClienteId', related_name='resenas')
    calificacion = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], db_column='Calificacion')
    comentario = models.CharField(max_length=1000, null=True, blank=True, db_column='Comentario')
    fecha = models.DateTimeField(default=timezone.now, db_column='Fecha')

    class Meta:
        managed = False
        db_table = 'Resena'
        verbose_name = 'reseña'


# =============================================================================
# 5. Ventas
# =============================================================================

class MetodoPago(ModeloConActivo):
    id = models.AutoField(primary_key=True, db_column='MetodoPagoId')
    nombre = models.CharField(max_length=40, unique=True, db_column='Nombre')

    class Meta:
        managed = False
        db_table = 'MetodoPago'
        verbose_name = 'método de pago'
        verbose_name_plural = 'métodos de pago'

    def __str__(self):
        return self.nombre


class Venta(ModeloConActivo):
    """Ventas de mostrador y pedidos en línea. Activo = 0 significa venta anulada."""

    class Canal(models.TextChoices):
        TIENDA = 'Tienda'
        EN_LINEA = 'En linea', 'En línea'

    class Estado(models.TextChoices):
        PENDIENTE = 'Pendiente'
        PAGADA = 'Pagada'
        PROCESANDO = 'Procesando'
        EN_CAMINO = 'En camino'
        ENTREGADO = 'Entregado'

    id = models.AutoField(primary_key=True, db_column='VentaId')
    numero_factura = models.CharField(max_length=20, unique=True, db_column='NumeroFactura')
    canal = models.CharField(max_length=10, choices=Canal.choices, db_column='Canal')
    cliente = models.ForeignKey(Cliente, models.PROTECT, null=True, blank=True, db_column='ClienteId',
                                related_name='ventas')
    usuario = models.ForeignKey(Usuario, models.PROTECT, null=True, blank=True, db_column='UsuarioId',
                                related_name='ventas')
    metodo_pago = models.ForeignKey(MetodoPago, models.PROTECT, db_column='MetodoPagoId', related_name='ventas')
    direccion_cliente = models.ForeignKey(DireccionCliente, models.PROTECT, null=True, blank=True,
                                          db_column='DireccionClienteId', related_name='ventas')
    direccion_envio = models.CharField(max_length=400, null=True, blank=True, db_column='DireccionEnvio')
    fecha = models.DateTimeField(default=timezone.now, db_column='Fecha')
    subtotal = dinero(12, validators=[MinValueValidator(0)], db_column='Subtotal')
    descuento = dinero(12, default=0, validators=[MinValueValidator(0)], db_column='Descuento')
    impuesto = dinero(12, default=0, validators=[MinValueValidator(0)], db_column='Impuesto')
    costo_envio = dinero(10, default=0, validators=[MinValueValidator(0)], db_column='CostoEnvio')
    # Columna calculada en SQL Server: no se escribe, solo se lee
    total = models.GeneratedField(
        expression=F('subtotal') - F('descuento') + F('impuesto') + F('costo_envio'),
        output_field=models.DecimalField(max_digits=15, decimal_places=2),
        db_persist=True, db_column='Total',
    )
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE, db_column='Estado')
    puntos_ganados = models.IntegerField(default=0, db_column='PuntosGanados')
    puntos_canjeados = models.IntegerField(default=0, db_column='PuntosCanjeados')
    notas = models.CharField(max_length=300, null=True, blank=True, db_column='Notas')

    class Meta:
        managed = False
        db_table = 'Venta'
        verbose_name = 'venta'
        ordering = ['-fecha']

    def __str__(self):
        return self.numero_factura


class DetalleVenta(ModeloNapo):
    id = models.AutoField(primary_key=True, db_column='DetalleVentaId')
    venta = models.ForeignKey(Venta, models.PROTECT, db_column='VentaId', related_name='detalles')
    producto = models.ForeignKey(Producto, models.PROTECT, db_column='ProductoId', related_name='detalles_venta')
    cantidad = models.IntegerField(validators=[MinValueValidator(1)], db_column='Cantidad')
    precio_unitario = dinero(validators=[MinValueValidator(0)], db_column='PrecioUnitario')
    descuento = dinero(default=0, validators=[MinValueValidator(0)], db_column='Descuento')
    # Columna calculada en SQL Server: no se escribe, solo se lee
    subtotal = models.GeneratedField(
        expression=F('cantidad') * F('precio_unitario') - F('descuento'),
        output_field=models.DecimalField(max_digits=22, decimal_places=2),
        db_persist=True, db_column='Subtotal',
    )

    class Meta:
        managed = False
        db_table = 'DetalleVenta'
        verbose_name = 'detalle de venta'


# =============================================================================
# 6. Devoluciones
# =============================================================================

class Devolucion(ModeloConActivo):
    class Motivo(models.TextChoices):
        DEFECTO = 'Defecto de fábrica'
        EQUIVOCADO = 'Producto equivocado'
        DANADO = 'Producto dañado'
        ALERGIA = 'Alergia o reacción'
        EXPECTATIVAS = 'No cumplió expectativas'
        OTRO = 'Otro'

    class TipoResolucion(models.TextChoices):
        REEMBOLSO = 'Reembolso'
        CAMBIO = 'Cambio'
        CREDITO = 'Crédito en tienda'

    class Estado(models.TextChoices):
        PENDIENTE = 'Pendiente'
        APROBADA = 'Aprobada'
        RECHAZADA = 'Rechazada'
        COMPLETADA = 'Completada'

    id = models.AutoField(primary_key=True, db_column='DevolucionId')
    venta = models.ForeignKey(Venta, models.PROTECT, db_column='VentaId', related_name='devoluciones')
    usuario = models.ForeignKey(Usuario, models.PROTECT, null=True, blank=True, db_column='UsuarioId',
                                related_name='devoluciones_revisadas')
    fecha_solicitud = models.DateTimeField(default=timezone.now, db_column='FechaSolicitud')
    fecha_resolucion = models.DateTimeField(null=True, blank=True, db_column='FechaResolucion')
    motivo = models.CharField(max_length=40, choices=Motivo.choices, db_column='Motivo')
    descripcion = models.CharField(max_length=500, null=True, blank=True, db_column='Descripcion')
    tipo_resolucion = models.CharField(max_length=20, choices=TipoResolucion.choices, db_column='TipoResolucion')
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE, db_column='Estado')
    monto_reembolso = dinero(12, default=0, validators=[MinValueValidator(0)], db_column='MontoReembolso')

    class Meta:
        managed = False
        db_table = 'Devolucion'
        verbose_name = 'devolución'
        verbose_name_plural = 'devoluciones'


class DetalleDevolucion(ModeloNapo):
    id = models.AutoField(primary_key=True, db_column='DetalleDevolucionId')
    devolucion = models.ForeignKey(Devolucion, models.PROTECT, db_column='DevolucionId', related_name='detalles')
    detalle_venta = models.ForeignKey(DetalleVenta, models.PROTECT, db_column='DetalleVentaId',
                                      related_name='devoluciones')
    cantidad = models.IntegerField(validators=[MinValueValidator(1)], db_column='Cantidad')
    regresa_a_inventario = models.BooleanField(default=False, db_column='RegresaAInventario')

    class Meta:
        managed = False
        db_table = 'DetalleDevolucion'
        verbose_name = 'detalle de devolución'
        verbose_name_plural = 'detalles de devoluciones'


# =============================================================================
# 7. Puntos y recompensas
# =============================================================================

class Recompensa(ModeloConActivo):
    class Tipo(models.TextChoices):
        ENVIO_GRATIS = 'Envio gratis', 'Envío gratis'
        REGALO = 'Regalo'
        DESCUENTO = 'Descuento'

    id = models.AutoField(primary_key=True, db_column='RecompensaId')
    nombre = models.CharField(max_length=100, db_column='Nombre')
    descripcion = models.CharField(max_length=300, null=True, blank=True, db_column='Descripcion')
    tipo = models.CharField(max_length=20, choices=Tipo.choices, db_column='Tipo')
    puntos_requeridos = models.IntegerField(validators=[MinValueValidator(1)], db_column='PuntosRequeridos')
    valor_descuento = dinero(null=True, blank=True, db_column='ValorDescuento')
    producto_regalo = models.ForeignKey(Producto, models.PROTECT, null=True, blank=True,
                                        db_column='ProductoRegaloId', related_name='recompensas_regalo')

    class Meta:
        managed = False
        db_table = 'Recompensa'
        verbose_name = 'recompensa'

    def __str__(self):
        return self.nombre


class MovimientoPuntos(ModeloNapo):
    """Historial inmutable de puntos."""

    class Tipo(models.TextChoices):
        GANADOS = 'Ganados'
        CANJEADOS = 'Canjeados'
        AJUSTE = 'Ajuste'
        VENCIDOS = 'Vencidos'

    id = models.AutoField(primary_key=True, db_column='MovimientoPuntosId')
    cliente = models.ForeignKey(Cliente, models.PROTECT, db_column='ClienteId', related_name='movimientos_puntos')
    tipo = models.CharField(max_length=20, choices=Tipo.choices, db_column='Tipo')
    puntos = models.IntegerField(db_column='Puntos')                # positivo suma, negativo resta
    venta = models.ForeignKey(Venta, models.PROTECT, null=True, blank=True, db_column='VentaId',
                              related_name='movimientos_puntos')
    recompensa = models.ForeignKey(Recompensa, models.PROTECT, null=True, blank=True, db_column='RecompensaId',
                                   related_name='canjes')
    descripcion = models.CharField(max_length=200, null=True, blank=True, db_column='Descripcion')
    fecha = models.DateTimeField(default=timezone.now, db_column='Fecha')

    class Meta:
        managed = False
        db_table = 'MovimientoPuntos'
        verbose_name = 'movimiento de puntos'
        verbose_name_plural = 'movimientos de puntos'
        ordering = ['-fecha']
