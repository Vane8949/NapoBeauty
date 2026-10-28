/* =============================================================================
   NAPO BEAUTY - Boceto de base de datos para SQL Server
   -----------------------------------------------------------------------------
   Cubre el panel de administración (productos, inventario, ventas, devoluciones,
   clientes, proveedores, usuarios y permisos, reportes) y la vista cliente
   (pedidos en línea, favoritos, lista de deseos, direcciones, métodos de pago,
   carrito, reseñas, puntos y recompensas).

   Convenciones:
     - Tablas en singular y PascalCase; llave primaria <Tabla>Id (INT IDENTITY).
     - Dinero en DECIMAL(10,2), córdobas (C$).
     - Fechas en DATETIME2 con valor por defecto SYSDATETIME().
     - Restricciones con nombre: PK_, FK_, UQ_, CK_, DF_; índices IX_ / UX_.
     - NADA SE BORRA: los registros se habilitan o deshabilitan con la columna
       Activo. Los triggers de la sección 9 bloquean cualquier DELETE.
     - Roles: Administrador (crea, edita, habilita/deshabilita) y
       Vendedor/Cajero (consulta y registra ventas).

   Ejecutar sobre una base de datos nueva (el script no borra nada).
   ============================================================================= */

IF DB_ID(N'NapoBeauty') IS NULL
    CREATE DATABASE NapoBeauty COLLATE Modern_Spanish_CI_AS;
GO
USE NapoBeauty;
GO

-- Necesarios para los índices filtrados (UX_...)
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO


/* =============================================================================
   1. SEGURIDAD: roles, permisos y usuarios del panel de administración
   ============================================================================= */

CREATE TABLE dbo.Rol (
    RolId           INT IDENTITY(1,1)  NOT NULL,
    Nombre          NVARCHAR(50)       NOT NULL,          -- Administrador, Vendedor/Cajero
    Descripcion     NVARCHAR(200)      NULL,
    Activo          BIT                NOT NULL CONSTRAINT DF_Rol_Activo DEFAULT (1),
    CONSTRAINT PK_Rol PRIMARY KEY (RolId),
    CONSTRAINT UQ_Rol_Nombre UNIQUE (Nombre)
);

CREATE TABLE dbo.Usuario (
    UsuarioId       INT IDENTITY(1,1)  NOT NULL,
    RolId           INT                NOT NULL,
    Nombre          NVARCHAR(80)       NOT NULL,
    Apellido        NVARCHAR(80)       NOT NULL,
    NombreUsuario   NVARCHAR(50)       NOT NULL,
    Correo          NVARCHAR(150)      NOT NULL,
    Telefono        NVARCHAR(20)       NULL,
    ContrasenaHash  NVARCHAR(255)      NOT NULL,          -- nunca la contraseña en texto plano
    FotoRuta        NVARCHAR(255)      NULL,
    Activo          BIT                NOT NULL CONSTRAINT DF_Usuario_Activo DEFAULT (1),
    UltimoAcceso    DATETIME2(0)       NULL,
    FechaCreacion   DATETIME2(0)       NOT NULL CONSTRAINT DF_Usuario_FechaCreacion DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_Usuario PRIMARY KEY (UsuarioId),
    CONSTRAINT UQ_Usuario_NombreUsuario UNIQUE (NombreUsuario),
    CONSTRAINT UQ_Usuario_Correo UNIQUE (Correo),
    CONSTRAINT FK_Usuario_Rol FOREIGN KEY (RolId) REFERENCES dbo.Rol (RolId)
);

-- Catálogo de permisos: una fila por cada acción de cada módulo del panel
CREATE TABLE dbo.Permiso (
    PermisoId       INT IDENTITY(1,1)  NOT NULL,
    Codigo          NVARCHAR(60)       NOT NULL,          -- ej. 'productos.crear' (lo que se valida en el código)
    Modulo          NVARCHAR(40)       NOT NULL,          -- ej. 'productos'
    Accion          NVARCHAR(20)       NOT NULL,          -- ver, crear, editar, habilitar, exportar
    Descripcion     NVARCHAR(200)      NULL,
    Activo          BIT                NOT NULL CONSTRAINT DF_Permiso_Activo DEFAULT (1),
    CONSTRAINT PK_Permiso PRIMARY KEY (PermisoId),
    CONSTRAINT UQ_Permiso_Codigo UNIQUE (Codigo),
    CONSTRAINT UQ_Permiso_Modulo_Accion UNIQUE (Modulo, Accion),
    CONSTRAINT CK_Permiso_Accion CHECK (Accion IN (N'ver', N'crear', N'editar', N'habilitar', N'exportar'))   -- 'habilitar' = habilitar o deshabilitar
);

-- Qué permisos tiene cada rol (relación muchos a muchos).
-- Para quitarle un permiso a un rol se pone Activo = 0.
CREATE TABLE dbo.RolPermiso (
    RolId           INT                NOT NULL,
    PermisoId       INT                NOT NULL,
    Activo          BIT                NOT NULL CONSTRAINT DF_RolPermiso_Activo DEFAULT (1),
    FechaAsignacion DATETIME2(0)       NOT NULL CONSTRAINT DF_RolPermiso_Fecha DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_RolPermiso PRIMARY KEY (RolId, PermisoId),
    CONSTRAINT FK_RolPermiso_Rol FOREIGN KEY (RolId) REFERENCES dbo.Rol (RolId),
    CONSTRAINT FK_RolPermiso_Permiso FOREIGN KEY (PermisoId) REFERENCES dbo.Permiso (PermisoId)
);
CREATE INDEX IX_RolPermiso_PermisoId ON dbo.RolPermiso (PermisoId);


/* =============================================================================
   2. CATÁLOGO: categorías, marcas, proveedores y productos
   ============================================================================= */

-- Una sola tabla para categorías y subcategorías (CategoriaPadreId NULL = categoría principal)
CREATE TABLE dbo.Categoria (
    CategoriaId       INT IDENTITY(1,1) NOT NULL,
    CategoriaPadreId  INT               NULL,
    Nombre            NVARCHAR(80)      NOT NULL,
    Icono             NVARCHAR(50)      NULL,             -- clase Font Awesome, ej. 'fa-palette'
    Orden             INT               NOT NULL CONSTRAINT DF_Categoria_Orden DEFAULT (0),
    Activo            BIT               NOT NULL CONSTRAINT DF_Categoria_Activo DEFAULT (1),
    CONSTRAINT PK_Categoria PRIMARY KEY (CategoriaId),
    CONSTRAINT UQ_Categoria_Padre_Nombre UNIQUE (CategoriaPadreId, Nombre),
    CONSTRAINT FK_Categoria_Padre FOREIGN KEY (CategoriaPadreId) REFERENCES dbo.Categoria (CategoriaId)
);

CREATE TABLE dbo.Marca (
    MarcaId         INT IDENTITY(1,1)  NOT NULL,
    Nombre          NVARCHAR(80)       NOT NULL,
    Activo          BIT                NOT NULL CONSTRAINT DF_Marca_Activo DEFAULT (1),
    CONSTRAINT PK_Marca PRIMARY KEY (MarcaId),
    CONSTRAINT UQ_Marca_Nombre UNIQUE (Nombre)
);

CREATE TABLE dbo.Proveedor (
    ProveedorId     INT IDENTITY(1,1)  NOT NULL,
    NombreEmpresa   NVARCHAR(150)      NOT NULL,
    NombreContacto  NVARCHAR(120)      NULL,
    RUC             NVARCHAR(20)       NULL,
    Telefono        NVARCHAR(20)       NULL,
    Correo          NVARCHAR(150)      NULL,
    Direccion       NVARCHAR(300)      NULL,
    Activo          BIT                NOT NULL CONSTRAINT DF_Proveedor_Activo DEFAULT (1),
    FechaRegistro   DATETIME2(0)       NOT NULL CONSTRAINT DF_Proveedor_FechaRegistro DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_Proveedor PRIMARY KEY (ProveedorId)
);
-- RUC único, pero puede haber varios proveedores sin RUC registrado
CREATE UNIQUE INDEX UX_Proveedor_RUC ON dbo.Proveedor (RUC) WHERE RUC IS NOT NULL;

CREATE TABLE dbo.Producto (
    ProductoId      INT IDENTITY(1,1)  NOT NULL,
    SKU             NVARCHAR(30)       NOT NULL,
    Nombre          NVARCHAR(150)      NOT NULL,
    Descripcion     NVARCHAR(MAX)      NULL,
    CategoriaId     INT                NOT NULL,          -- normalmente una subcategoría
    MarcaId         INT                NOT NULL,
    ProveedorId     INT                NULL,              -- proveedor habitual
    PrecioCompra    DECIMAL(10,2)      NOT NULL CONSTRAINT DF_Producto_PrecioCompra DEFAULT (0),
    PrecioVenta     DECIMAL(10,2)      NOT NULL,
    StockActual     INT                NOT NULL CONSTRAINT DF_Producto_StockActual DEFAULT (0),
    StockMinimo     INT                NOT NULL CONSTRAINT DF_Producto_StockMinimo DEFAULT (5),
    Activo          BIT                NOT NULL CONSTRAINT DF_Producto_Activo DEFAULT (1),
    FechaCreacion   DATETIME2(0)       NOT NULL CONSTRAINT DF_Producto_FechaCreacion DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_Producto PRIMARY KEY (ProductoId),
    CONSTRAINT UQ_Producto_SKU UNIQUE (SKU),
    CONSTRAINT FK_Producto_Categoria FOREIGN KEY (CategoriaId) REFERENCES dbo.Categoria (CategoriaId),
    CONSTRAINT FK_Producto_Marca FOREIGN KEY (MarcaId) REFERENCES dbo.Marca (MarcaId),
    CONSTRAINT FK_Producto_Proveedor FOREIGN KEY (ProveedorId) REFERENCES dbo.Proveedor (ProveedorId),
    CONSTRAINT CK_Producto_Precios CHECK (PrecioCompra >= 0 AND PrecioVenta >= 0),
    CONSTRAINT CK_Producto_Stock CHECK (StockActual >= 0 AND StockMinimo >= 0)
);
CREATE INDEX IX_Producto_CategoriaId ON dbo.Producto (CategoriaId);
CREATE INDEX IX_Producto_MarcaId     ON dbo.Producto (MarcaId);
CREATE INDEX IX_Producto_ProveedorId ON dbo.Producto (ProveedorId);

CREATE TABLE dbo.ProductoImagen (
    ProductoImagenId INT IDENTITY(1,1) NOT NULL,
    ProductoId       INT               NOT NULL,
    Ruta             NVARCHAR(255)     NOT NULL,          -- ruta dentro de media/productos/
    EsPrincipal      BIT               NOT NULL CONSTRAINT DF_ProductoImagen_EsPrincipal DEFAULT (0),
    Orden            INT               NOT NULL CONSTRAINT DF_ProductoImagen_Orden DEFAULT (0),
    Activo           BIT               NOT NULL CONSTRAINT DF_ProductoImagen_Activo DEFAULT (1),
    CONSTRAINT PK_ProductoImagen PRIMARY KEY (ProductoImagenId),
    CONSTRAINT FK_ProductoImagen_Producto FOREIGN KEY (ProductoId) REFERENCES dbo.Producto (ProductoId)
);

-- Variantes de un producto (tono, talla o presentación), cada una con su propio stock.
-- Producto.StockActual es la suma de sus variantes; un producto sin variantes tiene una llamada 'Único'.
CREATE TABLE dbo.VarianteProducto (
    VarianteProductoId INT IDENTITY(1,1) NOT NULL,
    ProductoId       INT               NOT NULL,
    Nombre           NVARCHAR(80)      NOT NULL,          -- tono, talla o presentación; 'Único' si no tiene
    ColorHex         NVARCHAR(7)       NULL,              -- muestra del tono, ej. #C2185B
    SKU              NVARCHAR(40)      NULL,              -- código propio del tono (opcional)
    Imagen           NVARCHAR(255)     NULL,              -- foto del tono, ruta dentro de media/
    StockActual      INT               NOT NULL CONSTRAINT DF_VarianteProducto_Stock DEFAULT (0),
    StockMinimo      INT               NOT NULL CONSTRAINT DF_VarianteProducto_StockMinimo DEFAULT (5),
    Orden            INT               NOT NULL CONSTRAINT DF_VarianteProducto_Orden DEFAULT (0),
    FechaCreacion    DATETIME2(0)      NOT NULL CONSTRAINT DF_VarianteProducto_Fecha DEFAULT (SYSDATETIME()),
    Activo           BIT               NOT NULL CONSTRAINT DF_VarianteProducto_Activo DEFAULT (1),
    CONSTRAINT PK_VarianteProducto PRIMARY KEY (VarianteProductoId),
    CONSTRAINT FK_VarianteProducto_Producto FOREIGN KEY (ProductoId) REFERENCES dbo.Producto (ProductoId),
    CONSTRAINT UQ_VarianteProducto_Nombre UNIQUE (ProductoId, Nombre),
    CONSTRAINT CK_VarianteProducto_Stock CHECK (StockActual >= 0),
    CONSTRAINT CK_VarianteProducto_StockMinimo CHECK (StockMinimo >= 0),
    CONSTRAINT CK_VarianteProducto_Color CHECK (ColorHex IS NULL OR ColorHex LIKE '#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]')
);
CREATE INDEX IX_VarianteProducto_ProductoId ON dbo.VarianteProducto (ProductoId);
CREATE UNIQUE INDEX UX_VarianteProducto_SKU ON dbo.VarianteProducto (SKU) WHERE SKU IS NOT NULL;
-- Solo una imagen principal por producto
CREATE UNIQUE INDEX UX_ProductoImagen_Principal ON dbo.ProductoImagen (ProductoId) WHERE EsPrincipal = 1 AND Activo = 1;


/* =============================================================================
   3. COMPRAS A PROVEEDORES E INVENTARIO
   ============================================================================= */

CREATE TABLE dbo.Compra (
    CompraId        INT IDENTITY(1,1)  NOT NULL,
    ProveedorId     INT                NOT NULL,
    UsuarioId       INT                NOT NULL,          -- quién registró la compra
    NumeroFactura   NVARCHAR(30)       NULL,              -- factura del proveedor
    Fecha           DATETIME2(0)       NOT NULL CONSTRAINT DF_Compra_Fecha DEFAULT (SYSDATETIME()),
    Total           DECIMAL(12,2)      NOT NULL CONSTRAINT DF_Compra_Total DEFAULT (0),
    Estado          NVARCHAR(20)       NOT NULL CONSTRAINT DF_Compra_Estado DEFAULT (N'Recibida'),
    Observaciones   NVARCHAR(300)      NULL,
    Activo          BIT                NOT NULL CONSTRAINT DF_Compra_Activo DEFAULT (1),   -- 0 = compra anulada
    CONSTRAINT PK_Compra PRIMARY KEY (CompraId),
    CONSTRAINT FK_Compra_Proveedor FOREIGN KEY (ProveedorId) REFERENCES dbo.Proveedor (ProveedorId),
    CONSTRAINT FK_Compra_Usuario FOREIGN KEY (UsuarioId) REFERENCES dbo.Usuario (UsuarioId),
    CONSTRAINT CK_Compra_Estado CHECK (Estado IN (N'Pendiente', N'Recibida'))
);
CREATE INDEX IX_Compra_ProveedorId ON dbo.Compra (ProveedorId);

CREATE TABLE dbo.DetalleCompra (
    DetalleCompraId INT IDENTITY(1,1)  NOT NULL,
    CompraId        INT                NOT NULL,
    ProductoId      INT                NOT NULL,
    VarianteId      INT                NULL,              -- tono que entró
    Cantidad        INT                NOT NULL,
    CostoUnitario   DECIMAL(10,2)      NOT NULL,
    Subtotal        AS (Cantidad * CostoUnitario) PERSISTED,
    CONSTRAINT PK_DetalleCompra PRIMARY KEY (DetalleCompraId),
    CONSTRAINT FK_DetalleCompra_Variante FOREIGN KEY (VarianteId) REFERENCES dbo.VarianteProducto (VarianteProductoId),
    CONSTRAINT FK_DetalleCompra_Compra FOREIGN KEY (CompraId) REFERENCES dbo.Compra (CompraId),
    CONSTRAINT FK_DetalleCompra_Producto FOREIGN KEY (ProductoId) REFERENCES dbo.Producto (ProductoId),
    CONSTRAINT CK_DetalleCompra_Cantidad CHECK (Cantidad > 0),
    CONSTRAINT CK_DetalleCompra_Costo CHECK (CostoUnitario >= 0)
);
CREATE INDEX IX_DetalleCompra_ProductoId ON dbo.DetalleCompra (ProductoId);

-- Historial de todo cambio de stock (pantalla "Inventario" y botón "Ajustar stock").
-- Es inmutable: un error se corrige con un nuevo movimiento de tipo 'Ajuste'.
CREATE TABLE dbo.MovimientoInventario (
    MovimientoInventarioId INT IDENTITY(1,1) NOT NULL,
    ProductoId      INT                NOT NULL,
    VarianteId      INT                NULL,              -- tono cuyo stock cambió
    UsuarioId       INT                NULL,              -- NULL si lo generó una compra en línea
    Tipo            NVARCHAR(20)       NOT NULL,
    Cantidad        INT                NOT NULL,          -- positiva entra, negativa sale
    StockAnterior   INT                NOT NULL,          -- stock de la variante antes y después
    StockNuevo      INT                NOT NULL,
    Motivo          NVARCHAR(200)      NULL,
    TipoReferencia  NVARCHAR(20)       NULL,              -- 'Venta', 'Compra', 'Devolucion', 'DevProveedor'
    ReferenciaId    INT                NULL,              -- Id de la venta/compra/devolución
    Fecha           DATETIME2(0)       NOT NULL CONSTRAINT DF_MovimientoInventario_Fecha DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_MovimientoInventario PRIMARY KEY (MovimientoInventarioId),
    CONSTRAINT FK_MovimientoInventario_Producto FOREIGN KEY (ProductoId) REFERENCES dbo.Producto (ProductoId),
    CONSTRAINT FK_MovimientoInventario_Variante FOREIGN KEY (VarianteId) REFERENCES dbo.VarianteProducto (VarianteProductoId),
    CONSTRAINT FK_MovimientoInventario_Usuario FOREIGN KEY (UsuarioId) REFERENCES dbo.Usuario (UsuarioId),
    CONSTRAINT CK_MovimientoInventario_Tipo CHECK (Tipo IN (N'Entrada', N'Salida', N'Ajuste', N'Devolucion')),
    CONSTRAINT CK_MovimientoInventario_Cantidad CHECK (Cantidad <> 0),
    CONSTRAINT CK_MovimientoInventario_Stock CHECK (StockNuevo >= 0 AND StockNuevo = StockAnterior + Cantidad)
);
CREATE INDEX IX_MovimientoInventario_Producto_Fecha ON dbo.MovimientoInventario (ProductoId, Fecha);
CREATE INDEX IX_MovimientoInventario_VarianteId ON dbo.MovimientoInventario (VarianteId, Fecha DESC);


/* =============================================================================
   4. CLIENTES (panel "Clientes" y cuenta de la vista cliente)
   ============================================================================= */

CREATE TABLE dbo.Cliente (
    ClienteId        INT IDENTITY(1,1) NOT NULL,
    Nombre           NVARCHAR(80)      NOT NULL,
    Apellido         NVARCHAR(80)      NULL,
    Correo           NVARCHAR(150)     NULL,              -- obligatorio solo si tiene cuenta en línea
    Telefono         NVARCHAR(20)      NULL,
    ContrasenaHash   NVARCHAR(255)     NULL,              -- NULL = cliente de mostrador sin cuenta
    FechaNacimiento  DATE              NULL,
    PuntosDisponibles INT              NOT NULL CONSTRAINT DF_Cliente_Puntos DEFAULT (0),
    Activo           BIT               NOT NULL CONSTRAINT DF_Cliente_Activo DEFAULT (1),
    FechaRegistro    DATETIME2(0)      NOT NULL CONSTRAINT DF_Cliente_FechaRegistro DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_Cliente PRIMARY KEY (ClienteId),
    CONSTRAINT CK_Cliente_Puntos CHECK (PuntosDisponibles >= 0),
    CONSTRAINT CK_Cliente_CuentaConCorreo CHECK (ContrasenaHash IS NULL OR Correo IS NOT NULL)
);
-- Correo único, pero varios clientes de mostrador pueden no tenerlo
CREATE UNIQUE INDEX UX_Cliente_Correo ON dbo.Cliente (Correo) WHERE Correo IS NOT NULL;

CREATE TABLE dbo.DireccionCliente (
    DireccionClienteId INT IDENTITY(1,1) NOT NULL,
    ClienteId        INT               NOT NULL,
    Alias            NVARCHAR(50)      NOT NULL,          -- 'Casa', 'Trabajo'
    NombreRecibe     NVARCHAR(120)     NOT NULL,
    Telefono         NVARCHAR(20)      NOT NULL,
    Departamento     NVARCHAR(60)      NOT NULL,
    Municipio        NVARCHAR(60)      NOT NULL,
    DireccionExacta  NVARCHAR(300)     NOT NULL,
    PuntoReferencia  NVARCHAR(200)     NULL,
    EsPredeterminada BIT               NOT NULL CONSTRAINT DF_DireccionCliente_Predeterminada DEFAULT (0),
    Activo           BIT               NOT NULL CONSTRAINT DF_DireccionCliente_Activo DEFAULT (1),
    CONSTRAINT PK_DireccionCliente PRIMARY KEY (DireccionClienteId),
    CONSTRAINT FK_DireccionCliente_Cliente FOREIGN KEY (ClienteId) REFERENCES dbo.Cliente (ClienteId)
);
CREATE UNIQUE INDEX UX_DireccionCliente_Predeterminada ON dbo.DireccionCliente (ClienteId) WHERE EsPredeterminada = 1 AND Activo = 1;

-- Métodos de pago guardados por el cliente.
-- IMPORTANTE: nunca guardar el número completo ni el CVV de una tarjeta.
-- Solo el token que entrega la pasarela de pago y los últimos 4 dígitos para mostrar.
CREATE TABLE dbo.MetodoPagoCliente (
    MetodoPagoClienteId INT IDENTITY(1,1) NOT NULL,
    ClienteId        INT               NOT NULL,
    Tipo             NVARCHAR(20)      NOT NULL,
    MarcaTarjeta     NVARCHAR(20)      NULL,              -- Visa, Mastercard
    UltimosDigitos   CHAR(4)           NULL,
    MesVencimiento   TINYINT           NULL,
    AnioVencimiento  SMALLINT          NULL,
    TokenPasarela    NVARCHAR(255)     NULL,
    EsPredeterminado BIT               NOT NULL CONSTRAINT DF_MetodoPagoCliente_Predeterminado DEFAULT (0),
    Activo           BIT               NOT NULL CONSTRAINT DF_MetodoPagoCliente_Activo DEFAULT (1),
    CONSTRAINT PK_MetodoPagoCliente PRIMARY KEY (MetodoPagoClienteId),
    CONSTRAINT FK_MetodoPagoCliente_Cliente FOREIGN KEY (ClienteId) REFERENCES dbo.Cliente (ClienteId),
    CONSTRAINT CK_MetodoPagoCliente_Tipo CHECK (Tipo IN (N'Tarjeta', N'Transferencia', N'Billetera')),
    CONSTRAINT CK_MetodoPagoCliente_Mes CHECK (MesVencimiento IS NULL OR MesVencimiento BETWEEN 1 AND 12)
);
CREATE UNIQUE INDEX UX_MetodoPagoCliente_Predeterminado ON dbo.MetodoPagoCliente (ClienteId) WHERE EsPredeterminado = 1 AND Activo = 1;

CREATE TABLE dbo.Favorito (
    ClienteId        INT               NOT NULL,
    ProductoId       INT               NOT NULL,
    FechaAgregado    DATETIME2(0)      NOT NULL CONSTRAINT DF_Favorito_Fecha DEFAULT (SYSDATETIME()),
    Activo           BIT               NOT NULL CONSTRAINT DF_Favorito_Activo DEFAULT (1),   -- 0 = quitado por el cliente
    CONSTRAINT PK_Favorito PRIMARY KEY (ClienteId, ProductoId),
    CONSTRAINT FK_Favorito_Cliente FOREIGN KEY (ClienteId) REFERENCES dbo.Cliente (ClienteId),
    CONSTRAINT FK_Favorito_Producto FOREIGN KEY (ProductoId) REFERENCES dbo.Producto (ProductoId)
);

CREATE TABLE dbo.ListaDeseo (
    ClienteId        INT               NOT NULL,
    ProductoId       INT               NOT NULL,
    FechaAgregado    DATETIME2(0)      NOT NULL CONSTRAINT DF_ListaDeseo_Fecha DEFAULT (SYSDATETIME()),
    Activo           BIT               NOT NULL CONSTRAINT DF_ListaDeseo_Activo DEFAULT (1),   -- 0 = quitado por el cliente
    AvisarDisponible BIT               NOT NULL CONSTRAINT DF_ListaDeseo_Avisar DEFAULT (0),
    CONSTRAINT PK_ListaDeseo PRIMARY KEY (ClienteId, ProductoId),
    CONSTRAINT FK_ListaDeseo_Cliente FOREIGN KEY (ClienteId) REFERENCES dbo.Cliente (ClienteId),
    CONSTRAINT FK_ListaDeseo_Producto FOREIGN KEY (ProductoId) REFERENCES dbo.Producto (ProductoId)
);

CREATE TABLE dbo.CarritoItem (
    ClienteId        INT               NOT NULL,
    ProductoId       INT               NOT NULL,
    Cantidad         INT               NOT NULL CONSTRAINT DF_CarritoItem_Cantidad DEFAULT (1),
    FechaAgregado    DATETIME2(0)      NOT NULL CONSTRAINT DF_CarritoItem_Fecha DEFAULT (SYSDATETIME()),
    Activo           BIT               NOT NULL CONSTRAINT DF_CarritoItem_Activo DEFAULT (1),   -- 0 = quitado o ya comprado
    CONSTRAINT PK_CarritoItem PRIMARY KEY (ClienteId, ProductoId),
    CONSTRAINT FK_CarritoItem_Cliente FOREIGN KEY (ClienteId) REFERENCES dbo.Cliente (ClienteId),
    CONSTRAINT FK_CarritoItem_Producto FOREIGN KEY (ProductoId) REFERENCES dbo.Producto (ProductoId),
    CONSTRAINT CK_CarritoItem_Cantidad CHECK (Cantidad > 0)
);

CREATE TABLE dbo.Resena (
    ResenaId         INT IDENTITY(1,1) NOT NULL,
    ProductoId       INT               NOT NULL,
    ClienteId        INT               NOT NULL,
    Calificacion     TINYINT           NOT NULL,
    Comentario       NVARCHAR(1000)    NULL,
    Activo           BIT               NOT NULL CONSTRAINT DF_Resena_Activo DEFAULT (1),   -- 0 = oculta por el administrador
    Fecha            DATETIME2(0)      NOT NULL CONSTRAINT DF_Resena_Fecha DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_Resena PRIMARY KEY (ResenaId),
    CONSTRAINT UQ_Resena_Producto_Cliente UNIQUE (ProductoId, ClienteId),   -- una reseña por cliente y producto
    CONSTRAINT FK_Resena_Producto FOREIGN KEY (ProductoId) REFERENCES dbo.Producto (ProductoId),
    CONSTRAINT FK_Resena_Cliente FOREIGN KEY (ClienteId) REFERENCES dbo.Cliente (ClienteId),
    CONSTRAINT CK_Resena_Calificacion CHECK (Calificacion BETWEEN 1 AND 5)
);


/* =============================================================================
   5. VENTAS (en tienda física y pedidos en línea en una sola tabla)
   ============================================================================= */

CREATE TABLE dbo.MetodoPago (
    MetodoPagoId     INT IDENTITY(1,1) NOT NULL,
    Nombre           NVARCHAR(40)      NOT NULL,          -- Efectivo, Tarjeta, Transferencia
    Activo           BIT               NOT NULL CONSTRAINT DF_MetodoPago_Activo DEFAULT (1),
    CONSTRAINT PK_MetodoPago PRIMARY KEY (MetodoPagoId),
    CONSTRAINT UQ_MetodoPago_Nombre UNIQUE (Nombre)
);

CREATE TABLE dbo.Venta (
    VentaId          INT IDENTITY(1,1) NOT NULL,
    NumeroFactura    NVARCHAR(20)      NOT NULL,          -- ej. 'V-000123'
    Canal            NVARCHAR(10)      NOT NULL,          -- 'Tienda' (mostrador) o 'En linea'
    ClienteId        INT               NULL,              -- NULL = venta de mostrador sin cliente
    UsuarioId        INT               NULL,              -- vendedor; NULL en pedidos en línea
    MetodoPagoId     INT               NOT NULL,
    DireccionClienteId INT             NULL,              -- solo pedidos con envío
    DireccionEnvio   NVARCHAR(400)     NULL,              -- copia de la dirección al momento del pedido
    Fecha            DATETIME2(0)      NOT NULL CONSTRAINT DF_Venta_Fecha DEFAULT (SYSDATETIME()),
    Subtotal         DECIMAL(12,2)     NOT NULL,
    Descuento        DECIMAL(12,2)     NOT NULL CONSTRAINT DF_Venta_Descuento DEFAULT (0),
    Impuesto         DECIMAL(12,2)     NOT NULL CONSTRAINT DF_Venta_Impuesto DEFAULT (0),   -- IVA
    CostoEnvio       DECIMAL(10,2)     NOT NULL CONSTRAINT DF_Venta_CostoEnvio DEFAULT (0),
    Total            AS (Subtotal - Descuento + Impuesto + CostoEnvio) PERSISTED,
    Estado           NVARCHAR(20)      NOT NULL CONSTRAINT DF_Venta_Estado DEFAULT (N'Pendiente'),
    PuntosGanados    INT               NOT NULL CONSTRAINT DF_Venta_PuntosGanados DEFAULT (0),
    PuntosCanjeados  INT               NOT NULL CONSTRAINT DF_Venta_PuntosCanjeados DEFAULT (0),
    Notas            NVARCHAR(300)     NULL,
    Activo           BIT               NOT NULL CONSTRAINT DF_Venta_Activo DEFAULT (1),   -- 0 = venta anulada
    CONSTRAINT PK_Venta PRIMARY KEY (VentaId),
    CONSTRAINT UQ_Venta_NumeroFactura UNIQUE (NumeroFactura),
    CONSTRAINT FK_Venta_Cliente FOREIGN KEY (ClienteId) REFERENCES dbo.Cliente (ClienteId),
    CONSTRAINT FK_Venta_Usuario FOREIGN KEY (UsuarioId) REFERENCES dbo.Usuario (UsuarioId),
    CONSTRAINT FK_Venta_MetodoPago FOREIGN KEY (MetodoPagoId) REFERENCES dbo.MetodoPago (MetodoPagoId),
    CONSTRAINT FK_Venta_DireccionCliente FOREIGN KEY (DireccionClienteId) REFERENCES dbo.DireccionCliente (DireccionClienteId),
    CONSTRAINT CK_Venta_Canal CHECK (Canal IN (N'Tienda', N'En linea')),
    CONSTRAINT CK_Venta_Estado CHECK (Estado IN (N'Pendiente', N'Pagada', N'Procesando', N'En camino', N'Entregado')),
    CONSTRAINT CK_Venta_EnLineaConCliente CHECK (Canal = N'Tienda' OR ClienteId IS NOT NULL),
    CONSTRAINT CK_Venta_Montos CHECK (Subtotal >= 0 AND Descuento >= 0 AND Impuesto >= 0 AND CostoEnvio >= 0 AND Descuento <= Subtotal),
    CONSTRAINT CK_Venta_Puntos CHECK (PuntosGanados >= 0 AND PuntosCanjeados >= 0)
);
CREATE INDEX IX_Venta_ClienteId_Fecha ON dbo.Venta (ClienteId, Fecha DESC);
CREATE INDEX IX_Venta_Fecha           ON dbo.Venta (Fecha);
CREATE INDEX IX_Venta_Estado          ON dbo.Venta (Estado);

CREATE TABLE dbo.DetalleVenta (
    DetalleVentaId   INT IDENTITY(1,1) NOT NULL,
    VentaId          INT               NOT NULL,
    ProductoId       INT               NOT NULL,
    VarianteId       INT               NULL,              -- tono vendido
    Cantidad         INT               NOT NULL,
    PrecioUnitario   DECIMAL(10,2)     NOT NULL,          -- precio al momento de la venta
    Descuento        DECIMAL(10,2)     NOT NULL CONSTRAINT DF_DetalleVenta_Descuento DEFAULT (0),
    Subtotal         AS (Cantidad * PrecioUnitario - Descuento) PERSISTED,
    CONSTRAINT PK_DetalleVenta PRIMARY KEY (DetalleVentaId),
    CONSTRAINT FK_DetalleVenta_Variante FOREIGN KEY (VarianteId) REFERENCES dbo.VarianteProducto (VarianteProductoId),
    CONSTRAINT FK_DetalleVenta_Venta FOREIGN KEY (VentaId) REFERENCES dbo.Venta (VentaId),
    CONSTRAINT FK_DetalleVenta_Producto FOREIGN KEY (ProductoId) REFERENCES dbo.Producto (ProductoId),
    CONSTRAINT CK_DetalleVenta_Cantidad CHECK (Cantidad > 0),
    CONSTRAINT CK_DetalleVenta_Montos CHECK (PrecioUnitario >= 0 AND Descuento >= 0 AND Descuento <= Cantidad * PrecioUnitario)
);
CREATE INDEX IX_DetalleVenta_ProductoId ON dbo.DetalleVenta (ProductoId);
CREATE INDEX IX_DetalleVenta_VarianteId ON dbo.DetalleVenta (VarianteId);
CREATE UNIQUE INDEX UX_DetalleVenta_Venta_Variante ON dbo.DetalleVenta (VentaId, VarianteId) WHERE VarianteId IS NOT NULL;


/* =============================================================================
   6. DEVOLUCIONES
   ============================================================================= */

CREATE TABLE dbo.Devolucion (
    DevolucionId     INT IDENTITY(1,1) NOT NULL,
    VentaId          INT               NOT NULL,
    UsuarioId        INT               NULL,              -- quién la revisó/aprobó
    FechaSolicitud   DATETIME2(0)      NOT NULL CONSTRAINT DF_Devolucion_FechaSolicitud DEFAULT (SYSDATETIME()),
    FechaResolucion  DATETIME2(0)      NULL,
    Motivo           NVARCHAR(40)      NOT NULL,
    Descripcion      NVARCHAR(500)     NULL,
    TipoResolucion   NVARCHAR(20)      NOT NULL,
    Estado           NVARCHAR(20)      NOT NULL CONSTRAINT DF_Devolucion_Estado DEFAULT (N'Pendiente'),
    MontoReembolso   DECIMAL(12,2)     NOT NULL CONSTRAINT DF_Devolucion_Monto DEFAULT (0),
    Activo           BIT               NOT NULL CONSTRAINT DF_Devolucion_Activo DEFAULT (1),
    CONSTRAINT PK_Devolucion PRIMARY KEY (DevolucionId),
    CONSTRAINT FK_Devolucion_Venta FOREIGN KEY (VentaId) REFERENCES dbo.Venta (VentaId),
    CONSTRAINT FK_Devolucion_Usuario FOREIGN KEY (UsuarioId) REFERENCES dbo.Usuario (UsuarioId),
    CONSTRAINT CK_Devolucion_Motivo CHECK (Motivo IN (N'Defecto de fábrica', N'Producto equivocado', N'Producto dañado', N'Alergia o reacción', N'No cumplió expectativas', N'Otro')),
    CONSTRAINT CK_Devolucion_TipoResolucion CHECK (TipoResolucion IN (N'Reembolso', N'Cambio', N'Crédito en tienda')),
    CONSTRAINT CK_Devolucion_Estado CHECK (Estado IN (N'Pendiente', N'Aprobada', N'Rechazada', N'Completada')),
    CONSTRAINT CK_Devolucion_Monto CHECK (MontoReembolso >= 0)
);
CREATE INDEX IX_Devolucion_VentaId ON dbo.Devolucion (VentaId);
CREATE INDEX IX_Devolucion_Estado  ON dbo.Devolucion (Estado);

CREATE TABLE dbo.DetalleDevolucion (
    DetalleDevolucionId INT IDENTITY(1,1) NOT NULL,
    DevolucionId     INT               NOT NULL,
    DetalleVentaId   INT               NOT NULL,          -- qué línea de la venta se devuelve
    Cantidad         INT               NOT NULL,
    RegresaAInventario BIT             NOT NULL CONSTRAINT DF_DetalleDevolucion_Regresa DEFAULT (0),  -- 1 si Destino = 'Inventario'
    Destino          NVARCHAR(20)      NOT NULL CONSTRAINT DF_DetalleDevolucion_Destino DEFAULT (N'Inventario'),
    CONSTRAINT PK_DetalleDevolucion PRIMARY KEY (DetalleDevolucionId),
    CONSTRAINT UQ_DetalleDevolucion UNIQUE (DevolucionId, DetalleVentaId),
    CONSTRAINT FK_DetalleDevolucion_Devolucion FOREIGN KEY (DevolucionId) REFERENCES dbo.Devolucion (DevolucionId),
    CONSTRAINT FK_DetalleDevolucion_DetalleVenta FOREIGN KEY (DetalleVentaId) REFERENCES dbo.DetalleVenta (DetalleVentaId),
    CONSTRAINT CK_DetalleDevolucion_Cantidad CHECK (Cantidad > 0),
    -- Inventario: regresa al stock · Baja: se descarta · Proveedor: se le regresa al proveedor
    CONSTRAINT CK_DetalleDevolucion_Destino CHECK (Destino IN (N'Inventario', N'Baja', N'Proveedor'))
);

-- Productos que la tienda le devuelve a un proveedor (defectuosos, vencidos, pedido equivocado...).
-- Origen 'Inventario': salen del stock al registrarla. Origen 'Cliente': los devolvió un cliente.
CREATE TABLE dbo.DevolucionProveedor (
    DevolucionProveedorId INT IDENTITY(1,1) NOT NULL,
    ProveedorId      INT               NOT NULL,
    DevolucionId     INT               NULL,              -- si viene de la devolución de un cliente
    UsuarioId        INT               NULL,              -- quién la registró / resolvió
    Origen           NVARCHAR(20)      NOT NULL CONSTRAINT DF_DevolucionProveedor_Origen DEFAULT (N'Inventario'),
    Fecha            DATETIME2(0)      NOT NULL CONSTRAINT DF_DevolucionProveedor_Fecha DEFAULT (SYSDATETIME()),
    FechaResolucion  DATETIME2(0)      NULL,
    Motivo           NVARCHAR(40)      NOT NULL,
    Resolucion       NVARCHAR(20)      NOT NULL CONSTRAINT DF_DevolucionProveedor_Resolucion DEFAULT (N'Reposición'),
    Estado           NVARCHAR(20)      NOT NULL CONSTRAINT DF_DevolucionProveedor_Estado DEFAULT (N'Pendiente'),
    MontoCredito     DECIMAL(12,2)     NOT NULL CONSTRAINT DF_DevolucionProveedor_Monto DEFAULT (0),  -- nota de crédito o reembolso
    FacturaProveedor NVARCHAR(30)      NULL,              -- factura del proveedor donde vino el producto
    Descripcion      NVARCHAR(500)     NULL,
    Activo           BIT               NOT NULL CONSTRAINT DF_DevolucionProveedor_Activo DEFAULT (1),
    CONSTRAINT PK_DevolucionProveedor PRIMARY KEY (DevolucionProveedorId),
    CONSTRAINT FK_DevolucionProveedor_Proveedor FOREIGN KEY (ProveedorId) REFERENCES dbo.Proveedor (ProveedorId),
    CONSTRAINT FK_DevolucionProveedor_Devolucion FOREIGN KEY (DevolucionId) REFERENCES dbo.Devolucion (DevolucionId),
    CONSTRAINT FK_DevolucionProveedor_Usuario FOREIGN KEY (UsuarioId) REFERENCES dbo.Usuario (UsuarioId),
    CONSTRAINT CK_DevolucionProveedor_Origen CHECK (Origen IN (N'Inventario', N'Cliente')),
    CONSTRAINT CK_DevolucionProveedor_Motivo CHECK (Motivo IN (N'Defecto de fábrica', N'Producto vencido', N'Producto dañado', N'Error en el pedido', N'Otro')),
    CONSTRAINT CK_DevolucionProveedor_Resolucion CHECK (Resolucion IN (N'Reposición', N'Nota de crédito', N'Reembolso')),
    CONSTRAINT CK_DevolucionProveedor_Estado CHECK (Estado IN (N'Pendiente', N'Enviada', N'Completada', N'Rechazada')),
    CONSTRAINT CK_DevolucionProveedor_Monto CHECK (MontoCredito >= 0)
);
CREATE INDEX IX_DevolucionProveedor_ProveedorId ON dbo.DevolucionProveedor (ProveedorId);
CREATE INDEX IX_DevolucionProveedor_Estado      ON dbo.DevolucionProveedor (Estado);

CREATE TABLE dbo.DetalleDevolucionProveedor (
    DetalleDevolucionProveedorId INT IDENTITY(1,1) NOT NULL,
    DevolucionProveedorId INT          NOT NULL,
    ProductoId       INT               NOT NULL,
    VarianteId       INT               NULL,              -- tono devuelto
    Cantidad         INT               NOT NULL,
    CostoUnitario    DECIMAL(10,2)     NOT NULL,          -- precio de compra al momento de devolver
    Subtotal         AS (Cantidad * CostoUnitario) PERSISTED,
    CONSTRAINT PK_DetalleDevolucionProveedor PRIMARY KEY (DetalleDevolucionProveedorId),
    CONSTRAINT FK_DetalleDevolucionProveedor_Variante FOREIGN KEY (VarianteId) REFERENCES dbo.VarianteProducto (VarianteProductoId),
    CONSTRAINT FK_DetalleDevolucionProveedor_Devolucion FOREIGN KEY (DevolucionProveedorId) REFERENCES dbo.DevolucionProveedor (DevolucionProveedorId),
    CONSTRAINT FK_DetalleDevolucionProveedor_Producto FOREIGN KEY (ProductoId) REFERENCES dbo.Producto (ProductoId),
    CONSTRAINT CK_DetalleDevolucionProveedor_Cantidad CHECK (Cantidad > 0),
    CONSTRAINT CK_DetalleDevolucionProveedor_Costo CHECK (CostoUnitario >= 0)
);
CREATE INDEX IX_DetalleDevolucionProveedor_ProductoId ON dbo.DetalleDevolucionProveedor (ProductoId);
CREATE UNIQUE INDEX UX_DetalleDevolucionProveedor_Variante ON dbo.DetalleDevolucionProveedor (DevolucionProveedorId, VarianteId) WHERE VarianteId IS NOT NULL;


/* =============================================================================
   7. PUNTOS Y RECOMPENSAS (vista cliente)
   ============================================================================= */

CREATE TABLE dbo.Recompensa (
    RecompensaId     INT IDENTITY(1,1) NOT NULL,
    Nombre           NVARCHAR(100)     NOT NULL,
    Descripcion      NVARCHAR(300)     NULL,
    Tipo             NVARCHAR(20)      NOT NULL,
    PuntosRequeridos INT               NOT NULL,
    ValorDescuento   DECIMAL(10,2)     NULL,              -- solo para Tipo = 'Descuento'
    ProductoRegaloId INT               NULL,              -- solo para Tipo = 'Regalo'
    Activo           BIT               NOT NULL CONSTRAINT DF_Recompensa_Activo DEFAULT (1),
    CONSTRAINT PK_Recompensa PRIMARY KEY (RecompensaId),
    CONSTRAINT FK_Recompensa_Producto FOREIGN KEY (ProductoRegaloId) REFERENCES dbo.Producto (ProductoId),
    CONSTRAINT CK_Recompensa_Tipo CHECK (Tipo IN (N'Envio gratis', N'Regalo', N'Descuento')),
    CONSTRAINT CK_Recompensa_Puntos CHECK (PuntosRequeridos > 0)
);

-- Historial de puntos: el saldo (Cliente.PuntosDisponibles) es la suma de estos movimientos.
-- Es inmutable: un error se corrige con un movimiento de tipo 'Ajuste'.
CREATE TABLE dbo.MovimientoPuntos (
    MovimientoPuntosId INT IDENTITY(1,1) NOT NULL,
    ClienteId        INT               NOT NULL,
    Tipo             NVARCHAR(20)      NOT NULL,
    Puntos           INT               NOT NULL,          -- positivo suma, negativo resta
    VentaId          INT               NULL,
    RecompensaId     INT               NULL,
    Descripcion      NVARCHAR(200)     NULL,
    Fecha            DATETIME2(0)      NOT NULL CONSTRAINT DF_MovimientoPuntos_Fecha DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_MovimientoPuntos PRIMARY KEY (MovimientoPuntosId),
    CONSTRAINT FK_MovimientoPuntos_Cliente FOREIGN KEY (ClienteId) REFERENCES dbo.Cliente (ClienteId),
    CONSTRAINT FK_MovimientoPuntos_Venta FOREIGN KEY (VentaId) REFERENCES dbo.Venta (VentaId),
    CONSTRAINT FK_MovimientoPuntos_Recompensa FOREIGN KEY (RecompensaId) REFERENCES dbo.Recompensa (RecompensaId),
    CONSTRAINT CK_MovimientoPuntos_Tipo CHECK (Tipo IN (N'Ganados', N'Canjeados', N'Ajuste', N'Vencidos')),
    CONSTRAINT CK_MovimientoPuntos_Puntos CHECK (Puntos <> 0)
);
CREATE INDEX IX_MovimientoPuntos_ClienteId ON dbo.MovimientoPuntos (ClienteId, Fecha DESC);
GO


/* =============================================================================
   8. VISTAS PARA DASHBOARD Y REPORTES
   ============================================================================= */

-- Productos con stock en o por debajo del mínimo (alertas del dashboard/inventario)
CREATE VIEW dbo.vw_StockBajo AS
SELECT  p.ProductoId, p.SKU, p.Nombre, m.Nombre AS Marca, c.Nombre AS Categoria,
        p.StockActual, p.StockMinimo
FROM    dbo.Producto  p
JOIN    dbo.Marca     m ON m.MarcaId = p.MarcaId
JOIN    dbo.Categoria c ON c.CategoriaId = p.CategoriaId
WHERE   p.Activo = 1
  AND   p.StockActual <= p.StockMinimo;
GO

-- Ventas por día (gráfica "Ventas 7 días" del dashboard)
CREATE VIEW dbo.vw_VentasPorDia AS
SELECT  CAST(v.Fecha AS DATE) AS Dia,
        v.Canal,
        COUNT(*)              AS NumeroVentas,
        SUM(v.Total)          AS TotalVendido
FROM    dbo.Venta v
WHERE   v.Activo = 1
GROUP BY CAST(v.Fecha AS DATE), v.Canal;
GO

-- Productos más vendidos (gráfica de dona del dashboard y reportes)
CREATE VIEW dbo.vw_ProductosMasVendidos AS
SELECT  p.ProductoId, p.Nombre, m.Nombre AS Marca,
        SUM(d.Cantidad) AS UnidadesVendidas,
        SUM(d.Subtotal) AS Ingresos
FROM    dbo.DetalleVenta d
JOIN    dbo.Venta    v ON v.VentaId = d.VentaId
JOIN    dbo.Producto p ON p.ProductoId = d.ProductoId
JOIN    dbo.Marca    m ON m.MarcaId = p.MarcaId
WHERE   v.Activo = 1
GROUP BY p.ProductoId, p.Nombre, m.Nombre;
GO

-- Calificación promedio y número de reseñas (estrellas de la tarjeta de producto)
CREATE VIEW dbo.vw_CalificacionProducto AS
SELECT  r.ProductoId,
        CAST(AVG(CAST(r.Calificacion AS DECIMAL(3,2))) AS DECIMAL(3,2)) AS Promedio,
        COUNT(*) AS TotalResenas
FROM    dbo.Resena r
WHERE   r.Activo = 1
GROUP BY r.ProductoId;
GO

-- Resumen por cliente (panel "Clientes")
CREATE VIEW dbo.vw_ResumenCliente AS
SELECT  c.ClienteId, c.Nombre, c.Apellido, c.Correo, c.Telefono, c.PuntosDisponibles,
        COUNT(v.VentaId)          AS TotalCompras,
        ISNULL(SUM(v.Total), 0)   AS MontoTotalComprado,
        MAX(v.Fecha)              AS UltimaCompra
FROM    dbo.Cliente c
LEFT JOIN dbo.Venta v ON v.ClienteId = c.ClienteId AND v.Activo = 1
GROUP BY c.ClienteId, c.Nombre, c.Apellido, c.Correo, c.Telefono, c.PuntosDisponibles;
GO


/* =============================================================================
   9. PROTECCIÓN: no se permite borrar registros
   -----------------------------------------------------------------------------
   Cada tabla tiene un trigger INSTEAD OF DELETE que rechaza el borrado.
   Para "quitar" algo se usa:  UPDATE dbo.<Tabla> SET Activo = 0 WHERE ...
   ============================================================================= */

CREATE TRIGGER dbo.TR_Rol_NoBorrar ON dbo.Rol INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en Rol. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_Permiso_NoBorrar ON dbo.Permiso INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en Permiso. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_RolPermiso_NoBorrar ON dbo.RolPermiso INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en RolPermiso. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_Usuario_NoBorrar ON dbo.Usuario INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en Usuario. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_Categoria_NoBorrar ON dbo.Categoria INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en Categoria. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_Marca_NoBorrar ON dbo.Marca INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en Marca. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_Proveedor_NoBorrar ON dbo.Proveedor INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en Proveedor. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_Producto_NoBorrar ON dbo.Producto INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en Producto. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_VarianteProducto_NoBorrar ON dbo.VarianteProducto INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en VarianteProducto. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_ProductoImagen_NoBorrar ON dbo.ProductoImagen INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en ProductoImagen. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_Compra_NoBorrar ON dbo.Compra INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en Compra. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_Cliente_NoBorrar ON dbo.Cliente INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en Cliente. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_DireccionCliente_NoBorrar ON dbo.DireccionCliente INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en DireccionCliente. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_MetodoPagoCliente_NoBorrar ON dbo.MetodoPagoCliente INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en MetodoPagoCliente. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_Favorito_NoBorrar ON dbo.Favorito INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en Favorito. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_ListaDeseo_NoBorrar ON dbo.ListaDeseo INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en ListaDeseo. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_CarritoItem_NoBorrar ON dbo.CarritoItem INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en CarritoItem. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_Resena_NoBorrar ON dbo.Resena INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en Resena. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_MetodoPago_NoBorrar ON dbo.MetodoPago INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en MetodoPago. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_Venta_NoBorrar ON dbo.Venta INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en Venta. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_Devolucion_NoBorrar ON dbo.Devolucion INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en Devolucion. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_Recompensa_NoBorrar ON dbo.Recompensa INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en Recompensa. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_DetalleCompra_NoBorrar ON dbo.DetalleCompra INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en DetalleCompra. Deshabilite el documento principal (Compra) con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_DetalleVenta_NoBorrar ON dbo.DetalleVenta INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en DetalleVenta. Deshabilite el documento principal (Venta) con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_DetalleDevolucion_NoBorrar ON dbo.DetalleDevolucion INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en DetalleDevolucion. Deshabilite el documento principal (Devolucion) con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_DevolucionProveedor_NoBorrar ON dbo.DevolucionProveedor INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en DevolucionProveedor. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_DetalleDevolucionProveedor_NoBorrar ON dbo.DetalleDevolucionProveedor INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en DetalleDevolucionProveedor. Deshabilite el documento principal (DevolucionProveedor) con Activo = 0.', 1;
END;
GO

CREATE TRIGGER dbo.TR_MovimientoInventario_NoBorrar ON dbo.MovimientoInventario INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en MovimientoInventario. Es historial: corrija con un movimiento de tipo Ajuste.', 1;
END;
GO

CREATE TRIGGER dbo.TR_MovimientoPuntos_NoBorrar ON dbo.MovimientoPuntos INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en MovimientoPuntos. Es historial: corrija con un movimiento de tipo Ajuste.', 1;
END;
GO


/* =============================================================================
   10. DATOS INICIALES
   ============================================================================= */

INSERT INTO dbo.Rol (Nombre, Descripcion) VALUES
    (N'Administrador',   N'Acceso total: crea, edita, habilita y deshabilita registros'),
    (N'Vendedor/Cajero', N'Consulta información y registra ventas');

INSERT INTO dbo.MetodoPago (Nombre) VALUES
    (N'Efectivo'), (N'Tarjeta'), (N'Transferencia');

-- Permisos: cada módulo del panel con sus acciones (no existe 'eliminar': nada se borra)
INSERT INTO dbo.Permiso (Codigo, Modulo, Accion, Descripcion)
SELECT  m.Modulo + N'.' + a.Accion, m.Modulo, a.Accion,
        a.Verbo + N' ' + m.Nombre
FROM (VALUES
        (N'dashboard',    N'el dashboard'),
        (N'productos',    N'productos'),
        (N'inventario',   N'inventario'),
        (N'ventas',       N'ventas'),
        (N'devoluciones', N'devoluciones'),
        (N'clientes',     N'clientes'),
        (N'proveedores',  N'proveedores'),
        (N'reportes',     N'reportes'),
        (N'usuarios',     N'usuarios y permisos')
     ) AS m (Modulo, Nombre)
CROSS JOIN (VALUES
        (N'ver',       N'Ver'),
        (N'crear',     N'Crear'),
        (N'editar',    N'Editar'),
        (N'habilitar', N'Habilitar o deshabilitar'),
        (N'exportar',  N'Exportar')
     ) AS a (Accion, Verbo)
-- El dashboard solo se ve; los reportes se ven y exportan;
-- el inventario se ve, se ajusta (crear un movimiento) y se exporta
WHERE NOT (m.Modulo = N'dashboard'  AND a.Accion <> N'ver')
  AND NOT (m.Modulo = N'reportes'   AND a.Accion NOT IN (N'ver', N'exportar'))
  AND NOT (m.Modulo = N'inventario' AND a.Accion NOT IN (N'ver', N'crear', N'exportar'));

-- Administrador: todos los permisos (es el único que crea, edita, habilita y deshabilita)
INSERT INTO dbo.RolPermiso (RolId, PermisoId)
SELECT  r.RolId, p.PermisoId
FROM    dbo.Rol r CROSS JOIN dbo.Permiso p
WHERE   r.Nombre = N'Administrador';

-- Vendedor/Cajero: consulta los módulos de operación y registra ventas
INSERT INTO dbo.RolPermiso (RolId, PermisoId)
SELECT  r.RolId, p.PermisoId
FROM    dbo.Rol r JOIN dbo.Permiso p ON p.Codigo IN (
            N'dashboard.ver',
            N'productos.ver',
            N'inventario.ver',
            N'clientes.ver',
            N'devoluciones.ver',
            N'ventas.ver',
            N'ventas.crear'      -- registrar una venta en caja
        )
WHERE   r.Nombre = N'Vendedor/Cajero';

-- Categorías principales (las mismas del menú "Todas las categorías")
INSERT INTO dbo.Categoria (Nombre, Icono, Orden) VALUES
    (N'Maquillaje',           N'fa-palette',             1),
    (N'Cuidado de la piel',   N'fa-spa',                 2),
    (N'Cuidado del cabello',  N'fa-pump-soap',           3),
    (N'Fragancias',           N'fa-spray-can-sparkles',  4),
    (N'Brochas y accesorios', N'fa-paintbrush',          5),
    (N'Sets y regalos',       N'fa-gift',                6);

-- Subcategorías
INSERT INTO dbo.Categoria (Nombre, CategoriaPadreId, Orden)
SELECT  s.Nombre, c.CategoriaId, s.Orden
FROM (VALUES
        (N'Maquillaje',           N'Ojos',                 1),
        (N'Maquillaje',           N'Rostro',               2),
        (N'Maquillaje',           N'Labios',               3),
        (N'Maquillaje',           N'Uñas',                 4),
        (N'Cuidado de la piel',   N'Limpiadores',          1),
        (N'Cuidado de la piel',   N'Hidratantes',          2),
        (N'Cuidado de la piel',   N'Serums',               3),
        (N'Cuidado de la piel',   N'Protector solar',      4),
        (N'Cuidado del cabello',  N'Shampoo',              1),
        (N'Cuidado del cabello',  N'Acondicionadores',     2),
        (N'Cuidado del cabello',  N'Aceites y serums',     3),
        (N'Fragancias',           N'Perfumes',             1),
        (N'Fragancias',           N'Body mists',           2),
        (N'Brochas y accesorios', N'Brochas',              1),
        (N'Brochas y accesorios', N'Esponjas',             2),
        (N'Brochas y accesorios', N'Cosmetiqueras',        3),
        (N'Sets y regalos',       N'Kits',                 1),
        (N'Sets y regalos',       N'Ediciones especiales', 2)
     ) AS s (Padre, Nombre, Orden)
JOIN dbo.Categoria c ON c.Nombre = s.Padre AND c.CategoriaPadreId IS NULL;

INSERT INTO dbo.Marca (Nombre) VALUES
    (N'Maybelline'), (N'Fenty Beauty'), (N'Rare Beauty'), (N'Kérastase'),
    (N'Real Techniques'), (N'The Ordinary');

-- Recompensas que aparecen en "Tus puntos y recompensas"
INSERT INTO dbo.Recompensa (Nombre, Descripcion, Tipo, PuntosRequeridos) VALUES
    (N'Envío gratis',      N'Envío gratis en tu próximo pedido', N'Envio gratis', 150),
    (N'Regalo sorpresa',   N'Un producto de regalo',             N'Regalo',       200);
GO
