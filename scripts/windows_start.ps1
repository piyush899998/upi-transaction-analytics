# Run this from the project's root directory on Windows with Docker Desktop running.
$ErrorActionPreference = "Stop"
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
Write-Host "Dashboard: http://localhost:8501"
Write-Host "Worker logs: docker compose logs -f worker"
