namespace SADE_DashboardAPI.Models
{
    public class DashboardConfig
    {
        public int Id { get; set; }
        public string Nombre { get; set; } = string.Empty;
        public string Modulo { get; set; } = string.Empty;
        public string TipoVista { get; set; } = string.Empty;
        public string ProcedimientoSQL { get; set; } = string.Empty;
        public string EjeX { get; set; } = string.Empty;
        public string EjeY { get; set; } = string.Empty;
        public string ConfiguracionUI { get; set; } = string.Empty;
    }
}
