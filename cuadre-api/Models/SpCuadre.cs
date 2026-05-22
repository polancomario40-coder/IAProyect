using System;

namespace CuadreApi.Models;

public class SpCuadre
{
    public int Orden { get; set; }
    public string? Usuario { get; set; }
    public Guid? Idfactura { get; set; }
    public string? Registro { get; set; }
    public string? Numero { get; set; }
    public string? Cliente { get; set; }
    public DateTime? Fecha { get; set; }
    public string? Moneda { get; set; }
    public decimal Efectivo { get; set; }
    public decimal Tarjeta { get; set; }
    public decimal Cheque { get; set; }
    public decimal Otros { get; set; }
    public decimal? Credito { get; set; }
    public decimal Factura { get; set; }
    public decimal Recibos { get; set; }
    public decimal Gastos { get; set; }
}
