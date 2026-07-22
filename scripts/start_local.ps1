param(
    [int]$FrontendPort = 18080,
    [switch]$Build,
    [switch]$Logs
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host ""
Write-Host "================================================"
Write-Host "      JobMatch AI - Local Start"
Write-Host "================================================"
Write-Host ""

Write-Host "Checking Docker..."
try {
    docker info *> $null
    Write-Host "Docker is running"
} catch {
    Write-Host "Docker is not running or Docker Desktop is not ready." -ForegroundColor Red
    Write-Host "Please start Docker Desktop first, then run this script again."
    exit 1
}

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example"
    } else {
        New-Item -ItemType File -Path ".env" | Out-Null
        Write-Host "Created empty .env"
    }
}

$envText = Get-Content ".env" -Raw
if ($envText -notmatch "(?m)^FRONTEND_PORT=") {
    Add-Content ".env" ""
    Add-Content ".env" "FRONTEND_PORT=$FrontendPort"
    Write-Host "Added FRONTEND_PORT=$FrontendPort to .env"
} else {
    (Get-Content ".env") |
        ForEach-Object {
            if ($_ -match "^FRONTEND_PORT=") { "FRONTEND_PORT=$FrontendPort" } else { $_ }
        } |
        Set-Content ".env"
    Write-Host "Using FRONTEND_PORT=$FrontendPort"
}

Write-Host ""
Write-Host "Starting services..."
if ($Build) {
    docker compose up -d --build
} else {
    docker compose up -d
}

Write-Host ""
Write-Host "Current service status:"
docker compose ps

Write-Host ""
Write-Host "Access URLs:"
Write-Host "  Frontend:        http://localhost:$FrontendPort"
Write-Host "  Fusion demo:     http://localhost:$FrontendPort/fusion-demo"
Write-Host "  Backend API:     http://localhost:8000"
Write-Host "  API Docs:        http://localhost:8000/docs"
Write-Host "  Elasticsearch:   http://localhost:9200"
Write-Host "  Neo4j Browser:   http://localhost:7474"
Write-Host ""
Write-Host "Neo4j Login:"
Write-Host "  Username: neo4j"
Write-Host "  Password: password"
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  View logs:       docker compose logs -f"
Write-Host "  Backend logs:    docker compose logs -f backend"
Write-Host "  Frontend logs:   docker compose logs -f frontend"
Write-Host "  Stop services:   docker compose down"
Write-Host ""

if ($Logs) {
    docker compose logs -f
}
