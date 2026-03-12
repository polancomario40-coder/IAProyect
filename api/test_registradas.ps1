$body = '{"Usuario":"test", "Clave":"test"}'
$response = Invoke-RestMethod -Uri "http://localhost:5039/api/Login" -Method Post -ContentType "application/json" -Body $body
$token = $response.token

$headers = @{
    Authorization = "Bearer $token"
}

$empresas = Invoke-RestMethod -Uri "http://localhost:5039/api/usuario/empresas" -Method Get -Headers $headers
$empresaId = $empresas[0].idEmpresa

$headers.Add("X-Selected-Company", $empresaId)

$facturas = Invoke-RestMethod -Uri "http://localhost:5039/api/CxpDocumento/registradas" -Method Get -Headers $headers
$facturas | ConvertTo-Json -Depth 5
