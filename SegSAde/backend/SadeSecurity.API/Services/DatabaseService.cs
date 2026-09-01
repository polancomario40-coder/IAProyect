using System;
using Microsoft.Data.SqlClient;
using Microsoft.Extensions.Configuration;

namespace SadeSecurity.API.Services
{
    public interface IDatabaseService
    {
        SqlConnection GetRepositoryConnection();
        SqlConnection GetCompanyConnection(string connectionString);
        string GetCompanyConnectionString(Guid companyId);
    }

    public class DatabaseService : IDatabaseService
    {
        private readonly IConfiguration _configuration;
        private readonly ICryptoService _cryptoService;
        private readonly string _repositoryConnectionString;

        public DatabaseService(IConfiguration configuration, ICryptoService cryptoService)
        {
            _configuration = configuration;
            _cryptoService = cryptoService;
            _repositoryConnectionString = _configuration.GetConnectionString("RepositoryConnection") 
                ?? "Server=38.247.136.37,1442;Database=CBSRepository;User Id=sade;Password=sadeP@$$w0rd;TrustServerCertificate=True;Encrypt=True;";
        }

        public SqlConnection GetRepositoryConnection()
        {
            return new SqlConnection(_repositoryConnectionString);
        }

        public SqlConnection GetCompanyConnection(string connectionString)
        {
            return new SqlConnection(connectionString);
        }

        public string GetCompanyConnectionString(Guid companyId)
        {
            using (var conn = GetRepositoryConnection())
            {
                conn.Open();
                string query = "SELECT Servidor, BaseDatos, Trusted, UserId, UserPwd, Encriptada FROM cfgEmpresa WHERE idEmpresa = @idEmpresa";
                using (var cmd = new SqlCommand(query, conn))
                {
                    cmd.Parameters.AddWithValue("@idEmpresa", companyId);
                    using (var reader = cmd.ExecuteReader())
                    {
                        if (reader.Read())
                        {
                            string server = reader.GetString(0);
                            string database = reader.GetString(1);
                            bool trusted = reader.GetBoolean(2);
                            string userId = reader.IsDBNull(3) ? "" : reader.GetString(3);
                            string userPwd = reader.IsDBNull(4) ? "" : reader.GetString(4);
                            bool encriptada = reader.IsDBNull(5) ? false : reader.GetBoolean(5);

                            if (trusted)
                            {
                                return $"Server={server};Database={database};Trusted_Connection=True;TrustServerCertificate=True;Encrypt=True;";
                            }
                            else
                            {
                                string clearUser = encriptada ? _cryptoService.DeEncryptString(userId) : userId;
                                string clearPwd = encriptada ? _cryptoService.DeEncryptString(userPwd) : userPwd;
                                return $"Server={server};Database={database};User Id={clearUser};Password={clearPwd};TrustServerCertificate=True;Encrypt=True;";
                            }
                        }
                    }
                }
            }
            throw new Exception("Empresa no encontrada en el repositorio.");
        }
    }
}
