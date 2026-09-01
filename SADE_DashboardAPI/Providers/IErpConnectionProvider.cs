using System.Threading.Tasks;

namespace SADE_DashboardAPI.Providers
{
    public interface IErpConnectionProvider
    {
        Task<string> GetConnectionStringAsync();
    }
}
