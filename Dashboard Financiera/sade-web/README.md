# SADE Web — Dashboard Financiero de Préstamos

Aplicación web moderna para visualizar la cartera de préstamos del ERP SADE,
basada en la base de datos **Financiera** (SQL Server).

## Arquitectura

```
SQL Server "Financiera" → FastAPI (Python) → React + Tailwind
```

## Estructura de Archivos

```
sade-web/
├── sql/                        # Stored Procedures
│   ├── 01_sp_DashboardKPIs.sql
│   ├── 02_sp_CobrosporMes.sql
│   └── 03_sp_EstadoPrestamo.sql
├── backend/                    # API FastAPI
│   ├── main.py
│   ├── database.py
│   ├── requirements.txt
│   ├── .env.example            ← copia y renombra a .env
│   ├── models/
│   │   └── schemas.py
│   └── routers/
│       ├── dashboard.py
│       └── prestamos.py
└── frontend/                   # React + Vite + Tailwind
    ├── src/
    │   ├── App.jsx
    │   ├── main.jsx
    │   ├── pages/
    │   │   ├── Dashboard.jsx
    │   │   └── LoanDetail.jsx
    │   ├── components/
    │   │   ├── KPICard.jsx
    │   │   ├── SummaryBlock.jsx
    │   │   ├── CuotasTable.jsx
    │   │   ├── RecibosTable.jsx
    │   │   └── CobrosChart.jsx
    │   └── hooks/
    │       └── useApi.js
    ├── package.json
    └── vite.config.js
```

---

## 1. Instalar los Stored Procedures en SQL Server

Abre **SQL Server Management Studio** y ejecuta los 3 archivos de la carpeta `sql/`
en orden, contra la base de datos **Financiera**:

```sql
-- Ejecutar en orden:
-- 1. sql/01_sp_DashboardKPIs.sql
-- 2. sql/02_sp_CobrosporMes.sql
-- 3. sql/03_sp_EstadoPrestamo.sql
```

> **Nota:** Los SPs usan las columnas `anulado`, `idCxcPadre`, `fechaVencimiento`.
> Si en tu BD esas columnas tienen nombres distintos, ajústalos antes de ejecutar.

---

## 2. Configurar el Backend

### Requisitos
- Python 3.11+
- [ODBC Driver 17 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
  (o "SQL Server" si ya lo tienes instalado)

### Instalación

```powershell
cd backend

# Crear entorno virtual
python -m venv .venv
.venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt

# Configurar credenciales
Copy-Item .env.example .env
notepad .env        # ← edita DB_SERVER, DB_USERNAME, DB_PASSWORD
```

### Contenido del `.env`

```env
DB_SERVER=localhost\SQLEXPRESS   # o el nombre/IP de tu servidor
DB_DATABASE=Financiera
DB_USERNAME=sa
DB_PASSWORD=tu_contraseña
DB_DRIVER=ODBC Driver 17 for SQL Server
ALLOWED_ORIGINS=http://localhost:5173
```

### Ejecutar

```powershell
uvicorn main:app --reload --port 8000
```

- API disponible en: http://localhost:8000
- Documentación Swagger: http://localhost:8000/docs
- Health check: http://localhost:8000/health

---

## 3. Configurar el Frontend

### Requisitos
- Node.js 20+

### Instalación

```powershell
cd frontend
npm install
```

### Ejecutar en desarrollo

```powershell
npm run dev
```

- App disponible en: http://localhost:5173

> El proxy de Vite redirige `/api/*` → `http://localhost:8000` automáticamente.

### Build para producción

```powershell
npm run build
# Los archivos estáticos quedan en frontend/dist/
```

---

## 4. Endpoints de la API

| Método | URL | Descripción |
|--------|-----|-------------|
| `GET` | `/api/dashboard/kpis` | KPIs del panel principal |
| `GET` | `/api/dashboard/cobros-por-mes?meses=12` | Cobros por mes para el gráfico |
| `GET` | `/api/dashboard/` | KPIs + Gráfico en una sola llamada |
| `GET` | `/api/prestamos/{idCxc}` | Estado completo de un préstamo |
| `GET` | `/health` | Verificar conexión a DB |
| `GET` | `/docs` | Documentación Swagger UI |

---

## 5. Notas de Adaptación a tu BD

El SP `03_sp_EstadoPrestamo.sql` asume esta estructura de cuotas:
- Las cuotas tienen `idCxcPadre = idCxc` del préstamo padre
- Si las cuotas tienen `idTipoDocumento = 'CU'`, agregar esa condición en los filtros
- Las moras de cuota (ND tipo 13) están ligadas a la cuota vía `idCxcPadre = idCuota`

Si en tu BD las moras/intereses de cuota están ligadas directamente al préstamo padre,
ajusta la subconsulta en el RS 2 (Cuotas).

---

## Tecnologías

| Capa | Tecnología |
|------|-----------|
| Base de datos | SQL Server — db `Financiera` |
| Backend | Python 3.11 + FastAPI + pyodbc |
| Frontend | React 18 + Vite + Tailwind CSS 3 |
| Gráficos | Recharts |
| HTTP Client | TanStack Query (React Query) |
| Iconos | Lucide React |
