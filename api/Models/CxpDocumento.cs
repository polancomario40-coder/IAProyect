using System;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace CxpApi.Models;

[Table("cxpDocumentos")]
public class CxpDocumento
{
    [Key]
    public int IdDocumento { get; set; }
    
    public Guid GUIDDocumento { get; set; } = Guid.NewGuid();
    
    public int IdSuplidor { get; set; }
    
    [ForeignKey("IdSuplidor")]
    public virtual CxpSuplidor? Suplidor { get; set; }
    
    public DateTime FechaEmision { get; set; }
    
    public DateTime? Vencimiento { get; set; }
    
    [MaxLength(100)]
    public string? Referencia { get; set; }
    
    [MaxLength(19)]
    public string? CompFiscal { get; set; } // NCF
    
    [MaxLength(500)]
    public string? Concepto { get; set; }
    
    [Column(TypeName = "decimal(18,2)")]
    public decimal Valor { get; set; }
    
    [Column(TypeName = "decimal(18,2)")]
    public decimal MontoImpuestos { get; set; }
    
    [Column(TypeName = "decimal(18,2)")]
    [DatabaseGenerated(DatabaseGeneratedOption.Computed)]
    public decimal Total { get; set; }
    
    [MaxLength(20)]
    public string? RNC { get; set; }
    
    [MaxLength(200)]
    public string? Nombre { get; set; }
    
    [MaxLength(100)]
    public string Usuario { get; set; } // ID del usuario que registra
    
    public DateTime Fecha { get; set; } = DateTime.UtcNow;
    
    public DateTime FechaRegistro { get; set; } = DateTime.UtcNow;
    
    [MaxLength(10)]
    public string Status { get; set; } = "A";
    
    public DateTime FechaStatus { get; set; } = DateTime.UtcNow;
    

    
    public bool PendValidacion { get; set; } = true;
    
    public bool PendEnvioEcf { get; set; } = true;

    // Campos faltantes obligatorios heredados de Delphi
    public int idTrans { get; set; } = 1; // Factura de Compra
    public int idMoneda { get; set; } = 1; // DOP
    public short Dias { get; set; } = 0;
    public bool CodifManual { get; set; } = false;
    public bool MostrarenCxP { get; set; } = true;
    public short BienesServicio { get; set; } = 1;

    [Column(TypeName = "decimal(18,2)")]
    public decimal MontoDescuento { get; set; } = 0;

    [Column(TypeName = "decimal(18,2)")]
    public decimal MontoRetenciones { get; set; } = 0;

    [Column(TypeName = "decimal(18,2)")]
    [DatabaseGenerated(DatabaseGeneratedOption.Computed)]
    public decimal TotalNeto { get; set; }

    public double Tasa { get; set; } = 1;

    [Column(TypeName = "decimal(18,2)")]
    public decimal? montoFacturadoBienes { get; set; }

    [Column(TypeName = "decimal(18,2)")]
    public decimal? montoFacturadoServicios { get; set; }

    [Column(TypeName = "decimal(18,2)")]
    public decimal MontoItbisCosto { get; set; } = 0;

    [Column(TypeName = "decimal(18,2)")]
    public decimal MontoIsc { get; set; } = 0;

    [Column(TypeName = "decimal(18,2)")]
    public decimal OtrosImpuestos { get; set; } = 0;

    [Column(TypeName = "decimal(18,2)")]
    public decimal PropinaLegal { get; set; } = 0;

    public bool RetenerTotalFactura { get; set; } = false;

    // Campos restantes NO NULOS de Delphi
    // Campos restantes (Nullables según Schema)
    public int? idCuentaBanco { get; set; }
    
    [MaxLength(16)]
    public string idCuenta { get; set; } = "2000201"; // Debe tener un valor, probaremos con el genérico del ejemplo
    
    [MaxLength(3)]
    public string TipoDocOrigen { get; set; } = "";
    
    public int? DocOrigen { get; set; }
    
    [MaxLength(100)]
    public string NotaAdicional { get; set; } = "";
    
    [MaxLength(16)]
    public string idAuxiliar { get; set; } = "";
    
    [MaxLength(2)]
    public string idTipoIdentificacion { get; set; } = "";
    
    [MaxLength(2)]
    public string idClaseGasto { get; set; } = "";
    
    [MaxLength(1)]
    public string TipoAbono { get; set; } = "";
    
    [MaxLength(5)]
    public string BancoDestino { get; set; } = "";
    
    [MaxLength(20)]
    public string CuentaDestino { get; set; } = "";
    
    [MaxLength(16)]
    public string TipoGasto { get; set; } = "";
    
    [MaxLength(16)]
    public string OrdenCompra { get; set; } = "";
    
    [MaxLength(16)]
    public string idPartida { get; set; } = "";
    
    public int? idPagoForma { get; set; }
    
    [MaxLength(500)]
    public string UltError { get; set; } = "";
    
    [MaxLength(100)]
    public string TrackId { get; set; } = "";
    
    [MaxLength(10)]
    public string TipoNcf { get; set; } = "";
    
    [MaxLength(50)]
    public string CodigoSeguridadEcf { get; set; } = "";
    
    [MaxLength(50)]
    public string CompFiscalModificado { get; set; } = "";
    
    [MaxLength(50)]
    public string IdClaseGastoModificado { get; set; } = "";
    
    [MaxLength(50)]
    public string StatusEcf { get; set; } = "";
    
    public Guid? idOrden { get; set; }
    public Guid? idReferencia { get; set; }
    public DateTime? HoraEnvio { get; set; }
    public DateTime? FechaFirmaDigital { get; set; }
    public DateTime? FechaVenceNCF { get; set; }
    public DateTime? FechaCompFiscalModificado { get; set; }
}
