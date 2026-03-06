using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace CxpApi.Models;

[Table("segusergrpempresa")]
public class SegUserGrpEmpresa
{
    [Required]
    [Column("idSegUserGrp")]
    [MaxLength(30)]
    public string IdSegUserGrp { get; set; }

    [Required]
    [Column("idEmpresa")]
    public Guid IdEmpresa { get; set; }
}
