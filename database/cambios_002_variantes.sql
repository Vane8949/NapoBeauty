/* =============================================================================
   NAPO BEAUTY - Cambio 002: variantes (tonos) con stock propio
   -----------------------------------------------------------------------------
   Ejecutar UNA vez sobre la base NapoBeauty que ya existe (no borra nada), después
   del cambio 001. Si la base se crea desde cero con napobeauty_sqlserver.sql, este
   cambio ya viene incluido.

   1. VarianteProducto: cada tono, talla o presentación de un producto con su propio
      stock y stock mínimo. Producto.StockActual pasa a ser la suma de sus variantes.
   2. A cada producto que ya existe se le crea la variante 'Único' con el stock que
      tiene ahora, para que nada se descuadre.
   3. Columna VarianteId en MovimientoInventario, DetalleVenta, DetalleCompra y
      DetalleDevolucionProveedor (se llena con la variante 'Único' en lo existente).
   ============================================================================= */

USE NapoBeauty;
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* ---------- 1. Tabla de variantes ---------- */
IF OBJECT_ID(N'dbo.VarianteProducto', N'U') IS NULL
CREATE TABLE dbo.VarianteProducto (
    VarianteProductoId INT IDENTITY(1,1) NOT NULL,
    ProductoId       INT               NOT NULL,
    Nombre           NVARCHAR(80)      NOT NULL,          -- tono, talla o presentación; 'Único' si no tiene
    ColorHex         NVARCHAR(7)       NULL,              -- muestra del tono, ej. #C2185B
    SKU              NVARCHAR(40)      NULL,
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
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_VarianteProducto_ProductoId')
    CREATE INDEX IX_VarianteProducto_ProductoId ON dbo.VarianteProducto (ProductoId);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_VarianteProducto_SKU')
    CREATE UNIQUE INDEX UX_VarianteProducto_SKU ON dbo.VarianteProducto (SKU) WHERE SKU IS NOT NULL;
GO

CREATE OR ALTER TRIGGER dbo.TR_VarianteProducto_NoBorrar ON dbo.VarianteProducto INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en VarianteProducto. Deshabilite el registro con Activo = 0.', 1;
END;
GO

/* ---------- 2. Variante 'Único' para los productos que ya existen ---------- */
INSERT INTO dbo.VarianteProducto (ProductoId, Nombre, StockActual, StockMinimo)
SELECT  p.ProductoId, N'Único', p.StockActual, p.StockMinimo
FROM    dbo.Producto p
WHERE   NOT EXISTS (SELECT 1 FROM dbo.VarianteProducto v WHERE v.ProductoId = p.ProductoId);
GO

/* ---------- 3. VarianteId en movimientos, ventas, compras y devoluciones a proveedor ---------- */
IF COL_LENGTH(N'dbo.MovimientoInventario', N'VarianteId') IS NULL
    ALTER TABLE dbo.MovimientoInventario ADD VarianteId INT NULL
        CONSTRAINT FK_MovimientoInventario_Variante REFERENCES dbo.VarianteProducto (VarianteProductoId);
IF COL_LENGTH(N'dbo.DetalleVenta', N'VarianteId') IS NULL
    ALTER TABLE dbo.DetalleVenta ADD VarianteId INT NULL
        CONSTRAINT FK_DetalleVenta_Variante REFERENCES dbo.VarianteProducto (VarianteProductoId);
IF COL_LENGTH(N'dbo.DetalleCompra', N'VarianteId') IS NULL
    ALTER TABLE dbo.DetalleCompra ADD VarianteId INT NULL
        CONSTRAINT FK_DetalleCompra_Variante REFERENCES dbo.VarianteProducto (VarianteProductoId);
IF COL_LENGTH(N'dbo.DetalleDevolucionProveedor', N'VarianteId') IS NULL
    ALTER TABLE dbo.DetalleDevolucionProveedor ADD VarianteId INT NULL
        CONSTRAINT FK_DetalleDevolucionProveedor_Variante REFERENCES dbo.VarianteProducto (VarianteProductoId);
GO

UPDATE t SET VarianteId = v.VarianteProductoId
FROM dbo.MovimientoInventario t JOIN dbo.VarianteProducto v ON v.ProductoId = t.ProductoId AND v.Nombre = N'Único'
WHERE t.VarianteId IS NULL;
UPDATE t SET VarianteId = v.VarianteProductoId
FROM dbo.DetalleVenta t JOIN dbo.VarianteProducto v ON v.ProductoId = t.ProductoId AND v.Nombre = N'Único'
WHERE t.VarianteId IS NULL;
UPDATE t SET VarianteId = v.VarianteProductoId
FROM dbo.DetalleCompra t JOIN dbo.VarianteProducto v ON v.ProductoId = t.ProductoId AND v.Nombre = N'Único'
WHERE t.VarianteId IS NULL;
UPDATE t SET VarianteId = v.VarianteProductoId
FROM dbo.DetalleDevolucionProveedor t JOIN dbo.VarianteProducto v ON v.ProductoId = t.ProductoId AND v.Nombre = N'Único'
WHERE t.VarianteId IS NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_MovimientoInventario_VarianteId')
    CREATE INDEX IX_MovimientoInventario_VarianteId ON dbo.MovimientoInventario (VarianteId, Fecha DESC);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_DetalleVenta_VarianteId')
    CREATE INDEX IX_DetalleVenta_VarianteId ON dbo.DetalleVenta (VarianteId);
GO

-- En una venta un mismo producto puede ir en varios tonos:
-- la regla "un renglón por producto" pasa a "un renglón por variante".
IF OBJECT_ID(N'dbo.UQ_DetalleVenta_Venta_Producto', N'UQ') IS NOT NULL
    ALTER TABLE dbo.DetalleVenta DROP CONSTRAINT UQ_DetalleVenta_Venta_Producto;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_DetalleVenta_Venta_Variante')
    CREATE UNIQUE INDEX UX_DetalleVenta_Venta_Variante
        ON dbo.DetalleVenta (VentaId, VarianteId) WHERE VarianteId IS NOT NULL;
GO

-- Lo mismo en una devolución a proveedor:
-- la regla "un renglón por producto" pasa a "un renglón por variante".
IF OBJECT_ID(N'dbo.UQ_DetalleDevolucionProveedor', N'UQ') IS NOT NULL
    ALTER TABLE dbo.DetalleDevolucionProveedor DROP CONSTRAINT UQ_DetalleDevolucionProveedor;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_DetalleDevolucionProveedor_Variante')
    CREATE UNIQUE INDEX UX_DetalleDevolucionProveedor_Variante
        ON dbo.DetalleDevolucionProveedor (DevolucionProveedorId, VarianteId) WHERE VarianteId IS NOT NULL;
GO

PRINT N'Cambio 002 aplicado: cada producto tiene sus variantes (tonos) con stock propio.';
GO
