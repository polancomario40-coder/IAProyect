# Mapa de Base de Datos - SADE Security

Este documento describe la estructura y uso de los objetos de base de datos de SQL Server (tablas, procedimientos almacenados y lógica) utilizados por el módulo de Seguridad de SADE ERP.

---

## 1. Base de Datos Central: `CBSRepository`

Gestiona el catálogo centralizado de usuarios, empresas y logs globales de auditoría.

### 1.1 Tablas Utilizadas

#### `SegUserGrp` (Catálogo de Usuarios y Grupos)
*   **Propósito**: Almacena las cuentas de usuario y los grupos del sistema a nivel global.
*   **Columnas Clave**:
    *   `idSegUserGrp` (varchar 30, PK): Identificador único de usuario o grupo (ej. `admin`, `G_VENTAS`).
    *   `Clave` (varchar 100): Contraseña cifrada con el algoritmo de SADE.
    *   `esGrupo` (bit): `0` = Usuario, `1` = Grupo.
    *   `Activo` (bit): Estado de la cuenta.
    *   `Nivel` (int): Nivel de clearance (1 a 5).
    *   `Nombre` (varchar 100): Nombre completo.
    *   `Email` (varchar 100): Correo para notificaciones.
    *   `Encriptada` (bit): Define si la clave almacenada está cifrada.

#### `cfgEmpresa` (Catálogo de Empresas / Tenants)
*   **Propósito**: Registra las empresas instaladas en SADE ERP y sus credenciales de conexión.
*   **Columnas Clave**:
    *   `idEmpresa` (uniqueidentifier, PK): Identificador único de empresa.
    *   `Empresa` (varchar 200): Nombre de la empresa.
    *   `Servidor` (varchar 50): Host/IP y puerto de SQL Server.
    *   `BaseDatos` (varchar 50): Nombre de la base de datos local (ej. `Financiera`).
    *   `Trusted` (bit): `1` = Windows Auth, `0` = SQL Server Auth.
    *   `UserId` (varchar 50): Usuario de SQL (cifrado si Encriptada = 1).
    *   `UserPwd` (nvarchar 50): Contraseña de SQL (cifrada si Encriptada = 1).
    *   `Activa` (bit): Estado de la empresa.
    *   `Encriptada` (bit): Define si `UserId` y `UserPwd` están encriptados.

#### `SegUserGrpEmpresa` (Mapeo Usuario-Empresa)
*   **Propósito**: Tabla de relación muchos-a-muchos que autoriza qué usuarios pueden conectarse a qué empresas.
*   **Columnas Clave**:
    *   `idEmpresa` (uniqueidentifier, FK)
    *   `idSegUserGrp` (varchar 30, FK)

#### `segLog` (Auditoría Central de Accesos)
*   **Propósito**: Guarda el log histórico de eventos de seguridad y acceso del sistema.
*   **Columnas Clave**:
    *   `idLog` (uniqueidentifier, PK)
    *   `idEmpresa` (uniqueidentifier, FK, Nullable)
    *   `fechaHora` (datetime): Registro temporal.
    *   `Usuario` (varchar 30)
    *   `Evento` (varchar 50): Identificador del evento (ej. `EVENT_LOGIN_OK`).
    *   `Objeto` (varchar 50): Pantalla u origen.
    *   `Descripcion` (varchar 200)

---

### 1.2 Procedimientos Almacenados (CBSRepository)

#### `cfgBuscarUsuario`
*   **Propósito**: Recupera el perfil del usuario para validar credenciales en el login.
*   **Parámetros**:
    *   `@idSegUserGrp` (varchar 30): Nombre de usuario.
*   **Retorno**: Fila única de `SegUserGrp`.

#### `cfgRSEmpresasXUsr`
*   **Propósito**: Obtiene la lista de empresas activas y autorizadas para el usuario conectado.
*   **Parámetros**:
    *   `@idSegUserGrp` (varchar 30): Nombre de usuario.
*   **Retorno**: Lista de registros de `cfgEmpresa`.

#### `cfgRSUsuario`
*   **Propósito**: Recupera todos los usuarios registrados a nivel global para la pantalla de administración.
*   **Retorno**: Lista de usuarios de `SegUserGrp` (esGrupo = 0).

#### `segInsertLog`
*   **Propósito**: Inserta un registro de auditoría en la tabla `segLog`.
*   **Parámetros**:
    *   `@idEmpresa` (uniqueidentifier), `@Usuario` (varchar 30), `@Evento` (varchar 50), `@Objeto` (varchar 50), `@Referencia` (varchar 50), `@Descripcion` (varchar 200), `@DatosAdd` (varchar 500).

---

## 2. Base de Datos Local de la Empresa: (ej. `Financiera`)

Contiene la matriz de permisos y reglas de seguridad locales para la empresa seleccionada.

### 2.1 Tablas Utilizadas

#### `SegObjeto` (Catálogo de Pantallas / Objetos del ERP)
*   **Propósito**: Registro técnico de todas las pantallas, reportes y acciones que requieren control de acceso.
*   **Columnas Clave**:
    *   `idSegObjeto` (varchar 40, PK): Nombre del objeto (ej. `FormFacturas`).
    *   `SegObjeto` (varchar 100): Descripción legible.
    *   `Categoria` (varchar 30): Módulo de negocio (CXC, Compras, Facturas).

#### `SegPermiso` (Matriz de Permisos Local)
*   **Propósito**: Define los niveles de acceso asignados a usuarios o grupos sobre cada objeto.
*   **Columnas Clave**:
    *   `idSegObjeto` (varchar 40, FK): Objeto relacionado.
    *   `idSegUserGrp` (varchar 30): Usuario o Grupo.
    *   Acciones: `Abrir`, `Agregar`, `Editar`, `Borrar`, `Imprimir`, `Anular`, `Aprobar` (tinyint).
        *   `0`: Denegado.
        *   `1..5`: Clearance nivel de usuario requerido para ejecutar.
        *   `6`: Acceso completo (Bypass).

#### `SegUserGrp` (Copia Local)
*   **Propósito**: Copia sincronizada local de los perfiles para realizar validaciones rápidas dentro de la base de datos de la empresa.

#### `SegUserinGrp` (Mapeo de Grupos Locales)
*   **Propósito**: Define qué usuarios pertenecen a qué grupos dentro de la base de datos de la empresa.
*   **Columnas Clave**:
    *   `idSegUser` (varchar 30, FK): Nombre de usuario.
    *   `idSegGrupo` (varchar 30, FK): Nombre del grupo.

#### `Autorizacion` (Tokens de Override de Supervisor)
*   **Propósito**: Almacena llaves de un solo uso generadas previamente para permitir autorizaciones manuales en caliente.
*   **Columnas Clave**:
    *   `idAutorizacion` (varchar 10, PK): Token único (ej. `3A57F`).
    *   `Clase` (smallint): Nivel de clearance que otorga esta llave.
    *   `Usadopor` (varchar 30, Nullable): Usuario que consumió la llave.
    *   `Fecha` (datetime, Nullable): Momento del consumo.

#### Tablas de Lógica de Negocio Específicas
*   `AlmacenPermiso`: Relación de acceso a almacenes (`idAlmacen`, `idSegUserGrp`).
*   `cxcPermisoCredito` / `ocPermisoOC`: Rangos de montos y días autorizados para la aprobación de créditos y órdenes de compra.

---

### 2.2 Procedimientos Almacenados (Local Empresa)

#### `Permisos`
*   **Propósito**: Recupera los permisos máximos de un usuario para un objeto determinado (evaluando los permisos asignados a su usuario directo y a todos los grupos a los que pertenece en `SegUserinGrp`).
*   **Parámetros**:
    *   `@User` (varchar 30): Nombre de usuario.
    *   `@Objeto` (varchar 40): Nombre de la pantalla.
*   **Retorno**: Fila única con los permisos resultantes (`Abrir`, `Agregar`, etc.).

#### `AutorizacionChk`
*   **Propósito**: Valida y consume una llave de supervisor para un override.
*   **Parámetros**:
    *   `@idAutorizacion` (varchar 10), `@Clase` (smallint), `@Referencia` (varchar 16), `@Usadopor` (varchar 30), `@Descripcion` (varchar 100).
    *   `@OK` (bit, output): Retorna `1` si el token es válido y se consumió, `0` si falla.

#### `cxcTienePermisoCredito`
*   **Propósito**: Valida si el usuario tiene permiso para autorizar créditos de venta a un cliente (excedentes de límites y días vencidos).
*   **Parámetros**:
    *   `@idOrdenComp` (uniqueidentifier), `@usuario` (varchar 30).
*   **Retorno**: Bit `TienePermiso`.
