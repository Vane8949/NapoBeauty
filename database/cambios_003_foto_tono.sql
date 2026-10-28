/* =============================================================================
   NAPO BEAUTY - Cambio 003: foto propia de cada tono
   -----------------------------------------------------------------------------
   Ejecutar UNA vez sobre la base NapoBeauty, después del cambio 002 (no borra nada).
   Si la base se crea desde cero con napobeauty_sqlserver.sql, ya viene incluido.

   VarianteProducto.Imagen: foto del tono (ruta dentro de media/, igual que ProductoImagen.Ruta).
   El SKU de cada tono ya existe desde el cambio 002 (VarianteProducto.SKU).
   ============================================================================= */

USE NapoBeauty;
GO

IF COL_LENGTH(N'dbo.VarianteProducto', N'Imagen') IS NULL
    ALTER TABLE dbo.VarianteProducto ADD Imagen NVARCHAR(255) NULL;
GO

PRINT N'Cambio 003 aplicado: cada tono puede tener su propia foto.';
GO
