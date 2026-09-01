using System;

namespace SadeSecurity.API.Models
{
    public class LoginRequest
    {
        public string Username { get; set; } = string.Empty;
        public string Password { get; set; } = string.Empty;
    }

    public class LoginResponse
    {
        public string Token { get; set; } = string.Empty;
        public string Username { get; set; } = string.Empty;
        public string FullName { get; set; } = string.Empty;
        public string Email { get; set; } = string.Empty;
        public int Nivel { get; set; }
    }

    public class ChangePasswordRequest
    {
        public string Username { get; set; } = string.Empty;
        public string OldPassword { get; set; } = string.Empty;
        public string NewPassword { get; set; } = string.Empty;
    }

    public class SelectCompanyRequest
    {
        public string CompanyId { get; set; } = string.Empty;
    }

    public class CompanyDto
    {
        public Guid IdEmpresa { get; set; }
        public string Empresa { get; set; } = string.Empty;
        public string RNC { get; set; } = string.Empty;
        public string Servidor { get; set; } = string.Empty;
        public string BaseDatos { get; set; } = string.Empty;
        public bool Trusted { get; set; }
        public string UserId { get; set; } = string.Empty;
        public string UserPwd { get; set; } = string.Empty;
        public bool Activa { get; set; }
    }

    public class UserDto
    {
        public string IdSegUserGrp { get; set; } = string.Empty;
        public string Clave { get; set; } = string.Empty;
        public bool EsGrupo { get; set; }
        public string ObjetoDefault { get; set; } = string.Empty;
        public bool Activo { get; set; }
        public int Nivel { get; set; }
        public string Email { get; set; } = string.Empty;
        public string Nombre { get; set; } = string.Empty;
        public string PreguntaSecreta { get; set; } = string.Empty;
        public string Respuesta { get; set; } = string.Empty;
        public bool CambiarClave { get; set; }
        public string Telefono { get; set; } = string.Empty;
        public string FirmaCorreo { get; set; } = string.Empty;
        public DateTime? ClaveVence { get; set; }
        public string CodigoAutorizacion { get; set; } = string.Empty;
    }

    public class GroupDto
    {
        public string IdSegUserGrp { get; set; } = string.Empty;
        public bool EsGrupo { get; set; } = true;
        public bool Activo { get; set; } = true;
        public int Nivel { get; set; } = 3;
        public string Nombre { get; set; } = string.Empty;
    }

    public class UserGroupMappingRequest
    {
        public string Username { get; set; } = string.Empty;
        public string GroupId { get; set; } = string.Empty;
    }

    public class PermissionDto
    {
        public string IdSegObjeto { get; set; } = string.Empty;
        public string IdSegUserGrp { get; set; } = string.Empty;
        public string Categoria { get; set; } = string.Empty;
        public string SegObjeto { get; set; } = string.Empty;
        public byte Agregar { get; set; }
        public byte Editar { get; set; }
        public byte Borrar { get; set; }
        public byte Imprimir { get; set; }
        public byte Abrir { get; set; }
        public byte Anular { get; set; }
        public byte Aprobar { get; set; }
    }

    public class OverrideRequest
    {
        public string Clave { get; set; } = string.Empty;
        public int Clase { get; set; }
        public string Referencia { get; set; } = string.Empty;
        public string Descripcion { get; set; } = string.Empty;
    }

    public class ObjectDto
    {
        public string IdSegObjeto { get; set; } = string.Empty;
        public string SegObjeto { get; set; } = string.Empty;
        public string TipoObjeto { get; set; } = string.Empty;
        public string Categoria { get; set; } = string.Empty;
    }

    public class AuditLogDto
    {
        public Guid IdLog { get; set; }
        public Guid IdEmpresa { get; set; }
        public DateTime FechaHora { get; set; }
        public string Usuario { get; set; } = string.Empty;
        public string Estacion { get; set; } = string.Empty;
        public string Evento { get; set; } = string.Empty;
        public string Objeto { get; set; } = string.Empty;
        public string Referencia { get; set; } = string.Empty;
        public string Descripcion { get; set; } = string.Empty;
        public string DatosAdicionales { get; set; } = string.Empty;
    }
}
