using Microsoft.EntityFrameworkCore;
using AuthGeneral.Models;

namespace AuthGeneral.Data;

public class AuthDbContext : DbContext
{
    public AuthDbContext(DbContextOptions<AuthDbContext> options) : base(options)
    {
    }

    public DbSet<Usuario> Usuarios { get; set; }
    public DbSet<CfgEmpresa> Empresas { get; set; }
    public DbSet<SegUserGrpEmpresa> UsuarioEmpresas { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        // Configure composite key for SegUserGrpEmpresa
        modelBuilder.Entity<SegUserGrpEmpresa>()
            .HasKey(ue => new { ue.IdSegUserGrp, ue.IdEmpresa });
    }
}
