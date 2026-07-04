using CxpApi.Models;

namespace CxpApi.Services;

public interface ICxpExternoService
{
    Task<ResultadoOperacion> ProcesarFacturaExternaAsync(CxpFacturaExternaDto dto);
}
