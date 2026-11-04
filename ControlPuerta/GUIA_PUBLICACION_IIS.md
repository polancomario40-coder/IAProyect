# 🚀 Guía de Publicación en IIS — Sistema Control de Puerta y Conduces

Este paquete contiene la versión completa y actualizada de **Control de Puerta** (Frontend React SPA compilado y Backend .NET 8 API), lista para ser desplegada en el servidor IIS.

---

## 📦 1. Ubicación del Paquete Generado

- **Archivo comprimido listo para copiar al servidor:**
  `PUBLICACION_IIS_SADE\06_SITIO_CONTROL_PUERTA.zip` (9.1 MB)
- **Carpeta descomprimida de publicación:**
  `ControlPuerta\publish\`
  - `publish\frontend\` (React SPA compilado con `web.config` y URL Rewrite)
  - `publish\backend\` (API .NET Core 8 con `web.config` para `AspNetCoreModuleV2`)

---

## 🏗️ 2. Arquitectura de Despliegue en IIS

Existen dos opciones estándar según la infraestructura de dominios de tu servidor IIS:

### Opción A (Recomendada - Subdominios VMO):
- **Sitio Frontend:** `https://puerta.vmo.do` (apunta a `publish\frontend`)
- **Sitio Backend (API):** `https://sadegateapi.vmo.do` (apunta a `publish\backend`)

### Opción B (Sitio Único con Aplicación `/api`):
- **Sitio Principal:** `http://tudominio/` (apunta a `publish\frontend`)
- **Aplicación /api:** Clic derecho sobre el sitio en IIS -> **Add Application...** -> Alias: `api` -> Ruta física: `publish\backend`.

---

## 📋 3. Pasos de Instalación en el Servidor IIS

### Paso 1: Copiar y Descomprimir
1. Copia el archivo `06_SITIO_CONTROL_PUERTA.zip` al servidor IIS.
2. Descomprímelo en tu directorio de aplicaciones, por ejemplo:
   - `C:\inetpub\wwwroot\ControlPuerta` (o `D:\SADE_APPS\ControlPuerta`)
   - Quedarán las carpetas `frontend\` y `backend\`.

### Paso 2: Permisos de Carpeta
1. En el Explorador de Windows, clic derecho sobre la carpeta descomprimida -> **Propiedades** -> pestaña **Seguridad** -> **Editar**.
2. Agrega el usuario/grupo **`IIS_IUSRS`**.
3. Asígnale permisos de **Lectura y Ejecución**, **Mostrar el contenido de la carpeta** y **Lectura**. (Para la carpeta de logs o backend, permite **Modificar**).
4. Clic en **Aceptar**.

### Paso 3: Configurar el Application Pool (Grupo de Aplicaciones)
1. Abre **Internet Information Services (IIS) Manager**.
2. En el panel izquierdo, clic en **Application Pools** -> **Add Application Pool...**
3. Configuración:
   - **Name:** `ControlPuertaAppPool`
   - **.NET CLR Version:** **No Managed Code** (Sin código administrado).
   - **Managed pipeline mode:** **Integrated**.
4. Clic en **OK**.

### Paso 4: Configurar los Sitios en IIS
1. **Frontend:**
   - Clic derecho en **Sites** -> **Add Website...**
   - **Site name:** `ControlPuertaUI`
   - **Application pool:** `ControlPuertaAppPool`
   - **Physical path:** `C:\inetpub\wwwroot\ControlPuerta\frontend`
   - Configura el Binding (Puerto o Hostname deseado).
2. **Backend (API):**
   - Clic derecho en **Sites** -> **Add Website...** (o agregar aplicación `/api`)
   - **Site name:** `ControlPuertaAPI`
   - **Application pool:** `ControlPuertaAppPool`
   - **Physical path:** `C:\inetpub\wwwroot\ControlPuerta\backend`
   - Configura el Binding (Puerto o Hostname `sadegateapi.vmo.do`).

---

## ⚡ 4. Scripts de Mantenimiento Incluidos

Si en el futuro realizas cambios en el código:

1. **`COMPILAR_FRONTEND.bat`**:
   - Re-compila la interfaz React con Vite y actualiza automáticamente `publish\frontend`.
2. **`COMPILAR_BACKEND.bat`**:
   - Re-compila el backend en Release con .NET 8 y actualiza `publish\backend`.
3. **`PUBLICAR_TODO.bat`**:
   - Ejecuta ambos procesos en un solo clic.
