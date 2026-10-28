/* Unir el Lumi Le Liquid Blush SKU 630 (ProductoId 4) como tono "Berry" del SKU 635 (ProductoId 3).
   No borra nada: el tono pasa con sus 2 unidades, su SKU, su foto y su historial;
   el producto 630 queda deshabilitado con stock 0. Ejecutar UNA vez (F5). */
USE NapoBeauty;
SET XACT_ABORT ON;
BEGIN TRAN;

IF EXISTS (SELECT 1 FROM VarianteProducto WHERE ProductoId = 4 AND Nombre = N'Único')
BEGIN
    -- El tono que ya tiene el 635 se queda con su SKU y su foto
    UPDATE v SET SKU = COALESCE(v.SKU, N'635'),
        Imagen = COALESCE(v.Imagen, (SELECT TOP 1 i.Ruta FROM ProductoImagen i
                                     WHERE i.ProductoId = 3 AND i.Activo = 1 AND i.EsPrincipal = 1))
    FROM VarianteProducto v WHERE v.ProductoId = 3;

    -- El stock del 630 pasa a ser el tono Berry del 635
    UPDATE v SET Nombre = N'Berry', SKU = COALESCE(v.SKU, N'630'),
        Imagen = COALESCE(v.Imagen, (SELECT TOP 1 i.Ruta FROM ProductoImagen i
                                     WHERE i.ProductoId = 4 AND i.Activo = 1 AND i.EsPrincipal = 1)),
        Orden = (SELECT ISNULL(MAX(Orden), 0) + 1 FROM VarianteProducto WHERE ProductoId = 3),
        ProductoId = 3
    FROM VarianteProducto v WHERE v.ProductoId = 4 AND v.Nombre = N'Único';

    -- El historial se mueve con el tono
    UPDATE MovimientoInventario       SET ProductoId = 3 WHERE ProductoId = 4;
    UPDATE DetalleVenta               SET ProductoId = 3 WHERE ProductoId = 4;
    UPDATE DetalleCompra              SET ProductoId = 3 WHERE ProductoId = 4;
    UPDATE DetalleDevolucionProveedor SET ProductoId = 3 WHERE ProductoId = 4;

    -- Totales: el 635 suma sus dos tonos; el 630 queda deshabilitado y en 0
    UPDATE Producto SET
        StockActual = (SELECT ISNULL(SUM(StockActual), 0) FROM VarianteProducto WHERE ProductoId = 3),
        StockMinimo = (SELECT ISNULL(SUM(StockMinimo), 0) FROM VarianteProducto WHERE ProductoId = 3 AND Activo = 1)
    WHERE ProductoId = 3;
    UPDATE Producto SET StockActual = 0, StockMinimo = 0, Activo = 0 WHERE ProductoId = 4;
    PRINT N'Listo: el SKU 630 quedó como tono Berry del Lumi SKU 635.';
END
ELSE
    PRINT N'No se hizo nada: el SKU 630 ya no tiene su stock aparte (¿ya se unió?).';

COMMIT;

SELECT p.SKU AS Producto, v.Nombre AS Tono, v.SKU AS SkuTono, v.StockActual, v.StockMinimo, v.Imagen
FROM VarianteProducto v JOIN Producto p ON p.ProductoId = v.ProductoId WHERE v.ProductoId IN (3, 4);
SELECT ProductoId, SKU, Activo, StockActual, StockMinimo FROM Producto WHERE ProductoId IN (3, 4);
