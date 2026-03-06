using Microsoft.EntityFrameworkCore;
using CxpApi.Models;

namespace CxpApi.Data;

public class AuthDbContext : DbContext
{
    public AuthDbContext(DbContextOptions<AuthDbContext> options) : base(options) { }

    public DbSet<Usuario> Usuarios { get; set; }
    public DbSet<CfgEmpresa> Empresas { get; set; }
    public DbSet<SegUserGrpEmpresa> UsuarioEmpresas { get; set; }
    
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);
        
        modelBuilder.Entity<Usuario>().ToTable("segusergrp");
        modelBuilder.Entity<CfgEmpresa>().ToTable("cfgempresa");
        
        modelBuilder.Entity<SegUserGrpEmpresa>()
            .ToTable("segusergrpempresa")
            .HasKey(ue => new { ue.IdSegUserGrp, ue.IdEmpresa });
    }
}
