CREATE OR ALTER PROCEDURE prtConfirmarRecepcion
    @idEntradaCamion    UNIQUEIDENTIFIER,
    @FechaRecepcion     DATETIME2(0),
    @UsuarioRecepcion   NVARCHAR(50),
    @idEvidencia        UNIQUEIDENTIFIER,
    @CantidadRecibida   DECIMAL(18,4),
    @Notas              NVARCHAR(500)
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE prtEntradaCamion SET
        FechaRecepcion      = @FechaRecepcion,
        UsuarioRecepcion    = @UsuarioRecepcion,
        idEvidencia         = @idEvidencia,
        CantidadRecibida    = @CantidadRecibida,
        Notas               = ISNULL(@Notas, Notas),
        Status              = 'RECIBIDO',
        FechaModificacion   = GETDATE(),
        UsuarioModificacion = @UsuarioRecepcion
    WHERE idEntradaCamion = @idEntradaCamion;

    SELECT @@ROWCOUNT AS FilasAfectadas;
END;
