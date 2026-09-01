using System;
using System.Threading.Tasks;
using SADE_DashboardAPI.Models;

namespace SADE_DashboardAPI.Services
{
    public interface IDashboardService
    {
        Task<IEnumerable<dynamic>> GetDashboardMenuAsync();
        Task<DashboardResponse> GetDashboardDataAsync(int idIndicador, DateTime fechaDesde, DateTime fechaHasta);
    }
}
