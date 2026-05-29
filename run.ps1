# Roda pipeline e sobe o servidor Flask (com API de upload)
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    Write-Host "==> Pipeline inicial" -ForegroundColor Cyan
    python -m pipeline.run_all
    Write-Host "`n==> Servindo dashboard + API em http://localhost:8000" -ForegroundColor Cyan
    python -m pipeline.server
} finally {
    Pop-Location
}
