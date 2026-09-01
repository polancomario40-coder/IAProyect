# Referencia de API REST - SADE Security

Este documento describe los endpoints disponibles en la API de Seguridad de SADE ERP. Todos los endpoints (excepto Login) requieren el encabezado HTTP: `Authorization: Bearer <JWT_TOKEN>`.

---

## 1. Endpoints de Autenticación (`/api/auth`)

### `POST /api/auth/login`
*   **Descripción**: Autentica al usuario contra la base de datos global `CBSRepository`.
*   **Cuerpo de Petición (Request)**:
    ```json
    {
      "username": "CBSAdmin",
      "password": "sadePassword"
    }
    ```
*   **Respuesta (Response) - 200 OK**:
    ```json
    {
      "token": "eyJhbGciOi...",
      "username": "CBSAdmin",
      "fullName": "Administrador Principal",
      "email": "admin@sade.com",
      "nivel": 5
    }
    ```

### `GET /api/auth/companies`
*   **Descripción**: Lista las empresas en las que el usuario autenticado tiene permisos de acceso.
*   **Respuesta - 200 OK**:
    ```json
    [
      {
        "idEmpresa": "6f2d90a5-f0ee-4b07-bfd1-447551cc4b9f",
        "empresa": "Financiera Sade",
        "rnc": "101-08544-2",
        "servidor": "108.181.198.178,1438",
        "baseDatos": "Financiera",
        "trusted": false,
        "userId": "sa",
        "activa": true
      }
    ]
    ```

### `POST /api/auth/select-company`
*   **Descripción**: Conecta dinámicamente con la base de datos de la empresa y devuelve un token JWT final que contiene la cadena de conexión cifrada.
*   **Cuerpo de Petición**:
    ```json
    {
      "companyId": "6f2d90a5-f0ee-4b07-bfd1-447551cc4b9f"
    }
    ```
*   **Respuesta - 200 OK**:
    ```json
    {
      "token": "eyJhbGciOi...(token firmado con conexión)",
      "username": "CBSAdmin",
      "fullName": "Administrador Principal",
      "email": "admin@sade.com",
      "companyId": "6f2d90a5-f0ee-4b07-bfd1-447551cc4b9f",
      "companyName": "Financiera Sade"
    }
    ```

---

## 2. Endpoints de Usuarios (`/api/users`)

### `GET /api/users`
*   **Descripción**: Obtiene la lista de usuarios locales de la empresa conectada actual.
*   **Respuesta - 200 OK**:
    ```json
    [
      {
        "idSegUserGrp": "vendedor_01",
        "nombre": "Pedro Infante",
        "email": "pedro@sade.com",
        "activo": true,
        "nivel": 3
      }
    ]
    ```

### `POST /api/users`
*   **Descripción**: Crea un usuario en `CBSRepository` y localmente en la base de datos de la empresa actual.
*   **Cuerpo de Petición**:
    ```json
    {
      "idSegUserGrp": "vendedor_02",
      "clave": "temporalPwd123",
      "nombre": "Luis Miguel",
      "email": "luis@sade.com",
      "nivel": 3,
      "activo": true
    }
    ```

---

## 3. Endpoints de Grupos (`/api/groups`)

### `GET /api/groups`
*   **Descripción**: Lista los grupos de seguridad locales de la empresa.
*   **Respuesta - 200 OK**:
    ```json
    [
      {
        "idSegUserGrp": "G_VENTAS",
        "activo": true,
        "nivel": 3
      }
    ]
    ```

### `GET /api/groups/{groupId}/members`
*   **Descripción**: Lista los nombres de los usuarios pertenecientes al grupo.
*   **Respuesta - 200 OK**:
    ```json
    [
      "vendedor_01",
      "vendedor_02"
    ]
    ```

### `POST /api/groups/{groupId}/members`
*   **Descripción**: Registra los usuarios mapeados al grupo de seguridad (reemplaza anteriores mappings).
*   **Cuerpo de Petición**:
    ```json
    [
      "vendedor_01",
      "vendedor_02"
    ]
    ```

---

## 4. Endpoints de Permisos (`/api/permissions`)

### `GET /api/permissions/objects`
*   **Descripción**: Obtiene el catálogo de pantallas y objetos registrados en la base de datos de la empresa.
*   **Respuesta - 200 OK**:
    ```json
    [
      {
        "idSegObjeto": "FormFactura",
        "segObjeto": "Pantalla de Facturación",
        "categoria": "Ventas"
      }
    ]
    ```

### `GET /api/permissions/matrix?userOrGroupId={id}`
*   **Descripción**: Obtiene la matriz de permisos para el usuario o grupo indicado.
*   **Respuesta - 200 OK**:
    ```json
    [
      {
        "idSegObjeto": "FormFactura",
        "idSegUserGrp": "G_VENTAS",
        "categoria": "Ventas",
        "segObjeto": "Pantalla de Facturación",
        "abrir": 6,
        "agregar": 3,
        "editar": 3,
        "borrar": 0,
        "imprimir": 6,
        "anular": 0,
        "aprobar": 0
      }
    ]
    ```

### `POST /api/permissions/matrix`
*   **Descripción**: Guarda los cambios en la matriz de permisos (upsert).
*   **Cuerpo de Petición**: Lista de objetos de permisos con sus valores `0..6`.

### `POST /api/permissions/check`
*   **Descripción**: Valida si el usuario actual tiene acceso sobre un objeto y acción específica.
*   **Cuerpo de Petición**:
    ```json
    {
      "idSegObjeto": "FormFactura",
      "segObjeto": "editar"
    }
    ```
*   **Respuesta - 200 OK (Acceso Concedido)**:
    ```json
    {
      "allowed": true,
      "requireOverride": false,
      "message": "Permiso concedido."
    }
    ```
*   **Respuesta - 200 OK (Acceso Insuficiente - Requiere Override)**:
    ```json
    {
      "allowed": false,
      "requireOverride": true,
      "requiredClass": 4,
      "message": "La acción requiere autorización de un supervisor de nivel 4 o superior."
    }
    ```

### `POST /api/permissions/authorize`
*   **Descripción**: Valida y consume una llave de supervisor (`Autorizacion`) para anular un bloqueo por permiso insuficiente.
*   **Cuerpo de Petición**:
    ```json
    {
      "clave": "5B8C1",
      "clase": 4,
      "referencia": "FAC-00120",
      "descripcion": "Override de descuento de factura"
    }
    ```
*   **Respuesta - 200 OK**:
    ```json
    {
      "authorized": true,
      "message": "Autorización del supervisor validada y consumida con éxito."
    }
    ```

---

## 5. Endpoints de Logs de Auditoría (`/api/auditlogs`)

### `GET /api/auditlogs`
*   **Descripción**: Obtiene los últimos 200 eventos de seguridad y accesos del sistema correspondientes a la empresa seleccionada o globales.
*   **Respuesta - 200 OK**:
    ```json
    [
      {
        "idLog": "8f3d0a92-d3ee-4a0b-bfd1-447551cc4b9f",
        "fechaHora": "2026-06-29T18:05:00Z",
        "usuario": "vendedor_01",
        "evento": "EVENT_LOGIN_OK",
        "objeto": "Login",
        "descripcion": "Inicio de sesion exitoso en el portal web.",
        "datosAdicionales": "IP: 192.168.1.15"
      }
    ]
    ```
