$body = '{"Usuario":"test", "Clave":"test"}'
$response = Invoke-RestMethod -Uri "http://localhost:5039/api/Login" -Method Post -ContentType "application/json" -Body $body
$token = $response.token

$headers = @{
    Authorization = "Bearer $token"
    "X-Selected-Company" = "f8c1f9df-8b2b-47cc-997f-82ed13a10e71"
}

# we'll create a temporary endpoint via script editing or just remove the WHERE clause from CxpDocumentoController.cs
