# 📘 Guía de Publicación en IIS — Sistema VMO

Esta configuración sigue exactamente el mismo estándar arquitectónico que tus otros sitios publicados en **IIS (`SADEWEBSERVICE`)** como `04_ModuloLentes` y `03_ProduccionEmbarque`, utilizando **IIS como Reverse Proxy con ARR + URL Rewrite** hacia el servicio FastAPI / Uvicorn en el puerto **`8000`**.

---

## 🏗️ 1. Arquitectura del Despliegue

```
Internet / Red Local
        │ (HTTP : 80 o HTTPS : 443)
        ▼
┌────────────────────────────────────────────────────────┐
│             IIS (Servidor SADEWEBSERVICE)              │
│                 Sitio Web: VMO                         │
│  web.config (URL Rewrite + Reverse Proxy ARR)          │
│  * Límite de carga: 1 GB (para ZIPs y lotes de PDFs)   │
└───────────────────────────┬────────────────────────────┘
                            │ (http://127.0.0.1:8000)
                            ▼
┌────────────────────────────────────────────────────────┐
│           Servicio VMO (FastAPI / Uvicorn)             │
│        Corriendo en segundo plano en puerto 8000       │
└────────────────────────────────────────────────────────┘
```

---

## 📋 2. Requisitos Previos en el Servidor IIS

1. **Módulos de IIS necesarios:**
   - **URL Rewrite** (Reescritura de URL).
   - **Application Request Routing (ARR)** (disponible en `requestRouter_amd64.msi`).
   - *Habilitar Proxy en ARR:* En IIS Manager, haz clic en el nombre del servidor (raíz) -> doble clic en **Application Request Routing Cache** -> panel derecho **Server Proxy Settings...** -> marcar **Enable proxy** -> clic en **Apply**.

2. **Python en el Servidor:**
   - Tener instalado Python 3.10 o 3.11 y agregado al `PATH`.
   
3. **LibreOffice (Opcional pero recomendado):**
   - Para la exportación de estimaciones a PDF (`soffice.exe` en `C:\Program Files\LibreOffice\program\soffice.exe`).

---

## 🚀 3. Pasos para Configurar en IIS Manager

### Paso 3.1: Copiar la Carpeta al Servidor
Copia la carpeta de publicación (o descomprime `05_SITIO_VMO.zip`) en la ruta de tus aplicaciones en el servidor:
- Ejemplo: `C:\inetpub\wwwroot\VMO` o `D:\SADE_APPS\VMO`.

### Paso 3.2: Configurar Variables de Entorno (`.env`)
En la carpeta del sitio, abre el archivo `.env` y configura:
```env
LOGIN_USER=admin
LOGIN_PASS=tu_contraseña_segura
ANTHROPIC_API_KEY=tu_api_key_de_claude
PORT=8000
HOST=127.0.0.1
```

### Paso 3.3: Permisos de Carpetas (Lectura/Escritura)
Dado que VMO almacena bases de datos SQLite y archivos generados:
1. En el Explorador de Windows, clic derecho en la carpeta de la app -> **Propiedades** -> pestaña **Seguridad** -> **Editar**.
2. Agrega al grupo **`IIS_IUSRS`** y dale permisos de **Modificar / Lectura / Escritura**.
3. Clic en **Aceptar**.

### Paso 3.4: Crear el Sitio Web en IIS
1. Abre **Internet Information Services (IIS) Manager**.
2. Despliega tu servidor -> clic derecho en **`Sites`** -> **`Add Website...`** (o agrega una aplicación bajo un sitio existente).
3. Completa los campos:
   - **Site name:** `VMO`
   - **Physical path:** Selecciona la carpeta donde copiaste la aplicación (donde está el archivo `web.config`).
   - **Binding:**
     - Si usas subdominio con HTTPS:
       - **Type:** `https`
       - **Port:** `443`
       - **Host name:** `vmo.sade.com.do` *(o el nombre deseado)*
       - Marcar: **Require Server Name Indication**
       - **SSL Certificate:** Seleccionar tu certificado SSL.
     - Si es en puerto HTTP directo:
       - **Type:** `http`, asignar puerto libre (ej. `8080` o en el puerto `80` con hostname).
4. Clic en **OK**.

---

## ⚡ 4. Poner en Marcha el Servicio Backend

Dentro de la carpeta de la aplicación dispones de scripts listos:

1. **`instalar_dependencias.bat`** (Solo la primera vez):
   - Crea el entorno virtual `.venv`.
   - Instala todas las librerías necesarias de Python.
   - Inicializa las bases de datos SQLite.

2. **`habilitar_servicio.bat`**:
   - Inicia Uvicorn silenciosamente en segundo plano en el puerto `8000`.
   - Verifica que el puerto esté activo y listo para recibir tráfico de IIS.

3. **`ver_estado.bat`**:
   - Verifica si el servicio está corriendo y responde con HTTP 200.

4. **`iniciar_manual_consola.bat`**:
   - Inicia Uvicorn en una consola visible (ideal para ver logs en vivo o depurar).

5. **`detener_servicio.bat`**:
   - Detiene de forma segura el servicio en el puerto `8000`.

---

## 🔄 5. Inicio Automático con Windows (Reinicio del Servidor)

Para que el servicio VMO arranque automáticamente si el servidor físico o virtual se reinicia:

1. Abre el **Programador de tareas de Windows** (`taskschd.msc`).
2. Clic en **Crear tarea básica...**:
   - **Nombre:** `Servicio VMO FastAPI`
   - **Desencadenador:** `Al iniciar el equipo`
   - **Acción:** `Iniciar un programa`
   - **Programa o script:** `wscript.exe`
   - **Argumentos:** `"C:\inetpub\wwwroot\VMO\iniciar_oculto.vbs"` *(ajustar a la ruta real)*
   - **Iniciar en:** `"C:\inetpub\wwwroot\VMO"`
3. En las propiedades de la tarea, marca:
   - `Ejecutar tanto si el usuario inició sesión como si no`.
   - `Ejecutar con los privilegios más altos`.
