using System.Collections.Generic;

namespace SADE_DashboardAPI.Models
{
    public class DashboardResponse
    {
        public dynamic? Metadata { get; set; }
        public IEnumerable<dynamic>? Data { get; set; }
    }
}
