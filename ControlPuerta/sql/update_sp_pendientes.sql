CREATE OR ALTER PROCEDURE prtObtenerPendientesCierre
    @FechaDia DATETIME = NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF @FechaDia IS NULL SET @FechaDia = CAST(GETDATE() AS DATE);

    SELECT
        e.idEntradaCamion,
        e.Conduce,
        e.Placa,
        e.Transportista,
        e.NombreChofer,
        e.FechaEntrada,
        e.FechaRecepcion,
        e.idProducto,
        e.Producto,
        e.Status,
        e.idOrden,
        e.OrdenNumero,
        e.idEvidencia,
        e.Notas,
        e.Usuario,
        e.idPuerta,
        e.idTransportista,
        e.idChofer,
        e.idAlmacen,
        e.CantidadRecibida,
        0 AS TotalRegistros
    FROM prtEntradaCamion e
    WHERE CAST(e.FechaEntrada AS DATE) = CAST(@FechaDia AS DATE)
      AND e.Status = 'RECIBIDO' -- SOLO LOS RECIBIDOS SE PUEDEN CERRAR
    ORDER BY e.FechaEntrada;
END;
