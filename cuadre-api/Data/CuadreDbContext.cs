using Microsoft.EntityFrameworkCore;

namespace CuadreApi.Data;

public class CuadreDbContext : DbContext
{
    public CuadreDbContext(DbContextOptions<CuadreDbContext> options) : base(options)
    {
    }
}
