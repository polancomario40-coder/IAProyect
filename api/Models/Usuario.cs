using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace CxpApi.Models;

[Table("segusergrp")]
public class Usuario
{
    [Key]
    [Column("idSegUserGrp")]
    [MaxLength(30)]
    public string Username { get; set; }
    
    [Required]
    [Column("Clave")]
    [MaxLength(100)]
    public string Password { get; set; }
    
    public bool Activo { get; set; }
    
    [Column("esGrupo")]
    public bool EsGrupo { get; set; }
    
    public int Nivel { get; set; }
    
    [MaxLength(100)]
    public string Nombre { get; set; }
    
    [MaxLength(100)]
    public string? Email { get; set; }
    
    public bool CambiarClave { get; set; }
    
    public DateTime? ClaveVence { get; set; }
    
    public bool Encriptada { get; set; }
    
    public Guid GuidUserGrp { get; set; }
}
