using System;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace CxpApi.Models;

[Table("SegUserWebAuthn")]
public class SegUserWebAuthn
{
    [Key]
    public int Id { get; set; }
    
    [Required]
    [MaxLength(100)]
    public string Username { get; set; } = string.Empty;
    
    [Required]
    public byte[] CredentialId { get; set; } = new byte[0];
    
    [Required]
    public byte[] PublicKey { get; set; } = new byte[0];
    
    [Required]
    public byte[] UserHandle { get; set; } = new byte[0];
    
    public uint SignatureCounter { get; set; }
    
    [MaxLength(200)]
    public string CredType { get; set; } = string.Empty;
    
    public DateTime RegDate { get; set; } = DateTime.UtcNow;
    
    public Guid AaGuid { get; set; }
}
