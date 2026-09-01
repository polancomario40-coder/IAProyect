using Microsoft.Data.SqlClient;

namespace ControlPuertaAPI.Services;

/// <summary>
/// Fábrica de conexiones a las dos bases de datos del módulo.
/// Centraliza las cadenas de conexión y permite reemplazarlas por variables
/// de entorno en producción sin tocar código.
/// </summary>
public interface IConnectionFactory
{
    SqlConnection CreateErpConnection();
    SqlConnection CreateEvidenciasConnection();
}

public class ConnectionFactory : IConnectionFactory
{
    private readonly string _erpConnStr;
    private readonly string _evidenciasConnStr;

    public ConnectionFactory(IConfiguration config)
    {
        _erpConnStr = config.GetConnectionString("ErpConnection")
            ?? throw new InvalidOperationException("ConnectionStrings:ErpConnection no configurada.");
        _evidenciasConnStr = config.GetConnectionString("EvidenciasConnection")
            ?? throw new InvalidOperationException("ConnectionStrings:EvidenciasConnection no configurada.");
    }

    public SqlConnection CreateErpConnection() => new(_erpConnStr);
    public SqlConnection CreateEvidenciasConnection() => new(_evidenciasConnStr);
}
