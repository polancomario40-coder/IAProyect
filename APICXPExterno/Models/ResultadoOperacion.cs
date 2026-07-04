namespace CxpApi.Models;

public class ResultadoOperacion
{
    public bool Exito { get; set; }
    public string Mensaje { get; set; } = string.Empty;
    public object? Data { get; set; }

    public static ResultadoOperacion Exitoso(string mensaje = "Operación exitosa", object? data = null)
    {
        return new ResultadoOperacion { Exito = true, Mensaje = mensaje, Data = data };
    }

    public static ResultadoOperacion Fallido(string mensaje)
    {
        return new ResultadoOperacion { Exito = false, Mensaje = mensaje };
    }
}
