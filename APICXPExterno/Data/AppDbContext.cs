using Microsoft.EntityFrameworkCore;
using CxpApi.Models;

namespace CxpApi.Data;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<CxpSuplidor> CxpSuplidores { get; set; }
    public DbSet<CxpDocumento> CxpDocumentos { get; set; }
    
    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
    {
        if (!optionsBuilder.IsConfigured)
        {
            optionsBuilder.UseSqlServer("Name=ErpConnection");
        }
        
        optionsBuilder.EnableSensitiveDataLogging();
        optionsBuilder.LogTo(Console.WriteLine, Microsoft.Extensions.Logging.LogLevel.Information);
    }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);
        
        // Relaciones y Mapeo exacto
        modelBuilder.Entity<CxpSuplidor>().ToTable("cxpsuplidores");
        modelBuilder.Entity<CxpDocumento>().ToTable("cxpDocumentos");
        
        // Restricción única si lo deseas para evitar subidas dobles (opcional ajustado)
        modelBuilder.Entity<CxpDocumento>()
            .HasIndex(d => new { d.IdSuplidor, d.Referencia })
            .IsUnique();
    }
}
