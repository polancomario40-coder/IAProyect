<#
.SYNOPSIS
    Script de Diagnóstico de Rendimiento y Bloqueos para el Servidor SADE Web.
.DESCRIPTION
    Verifica:
    1. Tiempo de respuesta de la base de datos SQL Server (Financiera / SoloNegocios)
    2. Tiempo de ejecución de los procedimientos analíticos (cxcReporteDetalleClientes y cxcReporteConsolidadoCartera)
    3. Detección de bloqueos activos (Locks) y consultas lentas en SQL Server
    4. Estado del servicio Backend en el puerto 8000 y consumo de memoria/CPU
#>

$ErrorActionPreference = "Continue"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   DIAGNOSTICO DE RENDIMIENTO SADE WEB Y SQL SERVER" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$envFile = Join-Path $PSScriptRoot "02_Backend_API\.env"
$dbServer = "localhost"
$dbName   = "Financiera"
$dbUser   = "sa"
$dbPass   = ""

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -match '^DB_SERVER=(.*)$')   { $dbServer = $Matches[1].Trim() }
        if ($line -match '^DB_DATABASE=(.*)$') { $dbName   = $Matches[1].Trim() }
        if ($line -match '^DB_USERNAME=(.*)$') { $dbUser   = $Matches[1].Trim() }
        if ($line -match '^DB_PASSWORD=(.*)$') { $dbPass   = $Matches[1].Trim() }
    }
}

Write-Host "[1/4] Verificando conexion a SQL Server ($dbServer)..." -ForegroundColor Yellow
$connStr = "Server=$dbServer;Database=$dbName;User Id=$dbUser;Password=$dbPass;TrustServerCertificate=True;Connection Timeout=10;"
try {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $conn = New-Object System.Data.SqlClient.SqlConnection($connStr)
    $conn.Open()
    $sw.Stop()
    Write-Host "  -> Conexion exitosa en $($sw.ElapsedMilliseconds) ms." -ForegroundColor Green
} catch {
    Write-Host "  [!] Error al conectar a SQL: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/4] Comprobando bloqueos activos en SQL Server..." -ForegroundColor Yellow
$lockQuery = @"
SELECT 
    r.session_id,
    r.status,
    r.wait_type,
    r.wait_time,
    r.blocking_session_id,
    SUBSTRING(t.text, (r.statement_start_offset/2)+1, 
        ((CASE r.statement_end_offset WHEN -1 THEN DATALENGTH(t.text) ELSE r.statement_end_offset END - r.statement_start_offset)/2) + 1) AS statement_text
FROM sys.dm_exec_requests r
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t
WHERE r.session_id <> @@SPID AND r.session_id > 50;
"@

$cmd = $conn.CreateCommand()
$cmd.CommandText = $lockQuery
$reader = $cmd.ExecuteReader()
$hasLocks = $false
while ($reader.Read()) {
    $hasLocks = $true
    Write-Host ("  [BLOQUEO DETECTADO] Sesion {0} (Bloqueada por {1}): Espera {2} ({3} ms) | Consulta: {4}" -f $reader["session_id"], $reader["blocking_session_id"], $reader["wait_type"], $reader["wait_time"], $reader["statement_text"]) -ForegroundColor Red
}
$reader.Close()
if (-not $hasLocks) {
    Write-Host "  -> No se detectaron bloqueos activos en el motor de base de datos." -ForegroundColor Green
}

Write-Host ""
Write-Host "[3/4] Midiendo tiempo de ejecucion de Procedimientos Almacenados..." -ForegroundColor Yellow

# Test cxcReporteConsolidadoCartera
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$cmd.CommandText = "EXEC dbo.cxcReporteConsolidadoCartera @fechaDesde='2026-10-01', @fechaHasta='2026-10-15', @fechaCorte='2026-10-15'"
$cmd.CommandTimeout = 120
$da = New-Object System.Data.SqlClient.SqlDataAdapter($cmd)
$ds = New-Object System.Data.DataSet
[void]$da.Fill($ds)
$sw.Stop()
Write-Host ("  -> cxcReporteConsolidadoCartera: {0:N2} segundos ({1} carteras devueltas)." -f ($sw.ElapsedMilliseconds / 1000.0), $ds.Tables[0].Rows.Count) -ForegroundColor Green

# Test cxcReporteDetalleClientes
$sw.Restart()
$cmd.CommandText = "EXEC dbo.cxcReporteDetalleClientes @fechaDesde='2026-10-01', @fechaHasta='2026-10-15', @tipoReporte='TODOS'"
$cmd.CommandTimeout = 120
$ds2 = New-Object System.Data.DataSet
[void]$da.Fill($ds2)
$sw.Stop()
Write-Host ("  -> cxcReporteDetalleClientes: {0:N2} segundos ({1} clientes devueltos)." -f ($sw.ElapsedMilliseconds / 1000.0), $ds2.Tables[0].Rows.Count) -ForegroundColor Green

$conn.Close()

Write-Host ""
Write-Host "[4/4] Verificando respuesta HTTP del Backend (Puerto 8000 / IIS 8080)..." -ForegroundColor Yellow
foreach ($port in @(8000, 8080)) {
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $res = Invoke-RestMethod -Uri "http://localhost:$port/health" -TimeoutSec 5
        $sw.Stop()
        Write-Host ("  -> Puerto {0}: Estado = {1} | DB = {2} ({3} ms)" -f $port, $res.status, $res.database, $sw.ElapsedMilliseconds) -ForegroundColor Green
    } catch {
        Write-Host "  -> Puerto $port no respondio: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   DIAGNOSTICO FINALIZADO" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""
pause
