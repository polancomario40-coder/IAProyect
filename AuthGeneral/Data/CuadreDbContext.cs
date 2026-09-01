using Microsoft.EntityFrameworkCore;

namespace AuthGeneral.Data;

public class CuadreDbContext : DbContext
{
    public CuadreDbContext(DbContextOptions<CuadreDbContext> options) : base(options)
    {
    }
}
