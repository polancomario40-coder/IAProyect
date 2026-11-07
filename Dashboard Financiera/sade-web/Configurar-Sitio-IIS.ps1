param(
    [int]$Puerto = 8080,
    [string]$NombreSitio = "SADEWeb",
    [string]$RutaFrontend = "$PSScriptRoot\03_Frontend_SitioWeb",
    [string]$RutaDestinoIIS = "C:\inetpub\wwwroot\sade-web"
)

Import-Module WebAdministration -ErrorAction Stop

if (-not (Test-Path $RutaDestinoIIS)) {
    New-Item -ItemType Directory -Path $RutaDestinoIIS -Force | Out-Null
}
Copy-Item -Path (Join-Path $RutaFrontend "*") -Destination $RutaDestinoIIS -Recurse -Force

icacls $RutaDestinoIIS /grant "IIS_IUSRS:(OI)(CI)RX" /T /Q | Out-Null
icacls $RutaDestinoIIS /grant "IUSR:(OI)(CI)RX" /T /Q | Out-Null

if (Get-Website -Name $NombreSitio -ErrorAction SilentlyContinue) {
    Remove-Website -Name $NombreSitio
}

New-Website -Name $NombreSitio -Port $Puerto -PhysicalPath $RutaDestinoIIS -Force | Out-Null
Start-Website -Name $NombreSitio -ErrorAction SilentlyContinue
Write-Host "  -> Sitio IIS '$NombreSitio' publicado en $RutaDestinoIIS (Puerto $Puerto)." -ForegroundColor Green