/* =============================================================================
   NAPO BEAUTY - Cambio 001: devoluciones a proveedor
   -----------------------------------------------------------------------------
   Ejecutar UNA vez sobre la base NapoBeauty que ya existe (no borra nada).
   Si la base se crea desde cero con napobeauty_sqlserver.sql, este cambio ya
   viene incluido y no hace falta ejecutarlo.

   1. DetalleDevolucion.Destino: a dónde va cada producto que devuelve un cliente
      ('Inventario' regresa al stock, 'Baja' se descarta, 'Proveedor' se le regresa
      al proveedor).
   2. DevolucionProveedor y DetalleDevolucionProveedor: productos que la tienda le
      devuelve a un proveedor (defectuosos, vencidos, pedido equivocado...).
   3. Triggers que bloquean el DELETE en las tablas nuevas.
   ============================================================================= */

USE NapoBeauty;
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* ---------- 1. Destino de cada producto devuelto por un cliente ---------- */
IF COL_LENGTH(N'dbo.DetalleDevolucion', N'Destino') IS NULL
BEGIN
    ALTER TABLE dbo.DetalleDevolucion
        ADD Destino NVARCHAR(20) NOT NULL CONSTRAINT DF_DetalleDevolucion_Destino DEFAULT (N'Inventario');
END;
GO

-- Las devoluciones que ya existían: lo que no regresaba al stock queda como 'Baja'
UPDATE dbo.DetalleDevolucion SET Destino = N'Baja' WHERE RegresaAInventario = 0 AND Destino = N'Inventario';
GO

IF OBJECT_ID(N'dbo.CK_DetalleDevolucion_Destino', N'C') IS NULL
    ALTER TABLE dbo.DetalleDevolucion ADD CONSTRAINT CK_DetalleDevolucion_Destino
        CHECK (Destino IN (N'Inventario', N'Baja', N'Proveedor'));
GO

/* ---------- 2. Devoluciones a proveedor ---------- */
IF OBJECT_ID(N'dbo.DevolucionProveedor', N'U') IS NULL
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
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_DevolucionProveedor_ProveedorId')
    CREATE INDEX IX_DevolucionProveedor_ProveedorId ON dbo.DevolucionProveedor (ProveedorId);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_DevolucionProveedor_Estado')
    CREATE INDEX IX_DevolucionProveedor_Estado ON dbo.DevolucionProveedor (Estado);
GO

IF OBJECT_ID(N'dbo.DetalleDevolucionProveedor', N'U') IS NULL
CREATE TABLE dbo.DetalleDevolucionProveedor (
    DetalleDevolucionProveedorId INT IDENTITY(1,1) NOT NULL,
    DevolucionProveedorId INT          NOT NULL,
    ProductoId       INT               NOT NULL,
    Cantidad         INT               NOT NULL,
    CostoUnitario    DECIMAL(10,2)     NOT NULL,          -- precio de compra al momento de devolver
    Subtotal         AS (Cantidad * CostoUnitario) PERSISTED,
    CONSTRAINT PK_DetalleDevolucionProveedor PRIMARY KEY (DetalleDevolucionProveedorId),
    CONSTRAINT UQ_DetalleDevolucionProveedor UNIQUE (DevolucionProveedorId, ProductoId),
    CONSTRAINT FK_DetalleDevolucionProveedor_Devolucion FOREIGN KEY (DevolucionProveedorId) REFERENCES dbo.DevolucionProveedor (DevolucionProveedorId),
    CONSTRAINT FK_DetalleDevolucionProveedor_Producto FOREIGN KEY (ProductoId) REFERENCES dbo.Producto (ProductoId),
    CONSTRAINT CK_DetalleDevolucionProveedor_Cantidad CHECK (Cantidad > 0),
    CONSTRAINT CK_DetalleDevolucionProveedor_Costo CHECK (CostoUnitario >= 0)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_DetalleDevolucionProveedor_ProductoId')
    CREATE INDEX IX_DetalleDevolucionProveedor_ProductoId ON dbo.DetalleDevolucionProveedor (ProductoId);
GO

/* ---------- 3. Nada se borra ---------- */
CREATE OR ALTER TRIGGER dbo.TR_DevolucionProveedor_NoBorrar ON dbo.DevolucionProveedor INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en DevolucionProveedor. Deshabilite el registro con Activo = 0.', 1;
END;
GO

CREATE OR ALTER TRIGGER dbo.TR_DetalleDevolucionProveedor_NoBorrar ON dbo.DetalleDevolucionProveedor INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    THROW 50001, N'No se permite borrar en DetalleDevolucionProveedor. Deshabilite el documento principal (DevolucionProveedor) con Activo = 0.', 1;
END;
GO

PRINT N'Cambio 001 aplicado: devoluciones a proveedor listas.';
GO
