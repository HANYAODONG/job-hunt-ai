# Import bundled sample jobs into Elasticsearch and Neo4j.
# Run from the repository root after Docker services are healthy.

$ErrorActionPreference = "Stop"

$CsvPath = "jobs\SDE-Nov21.csv"
$ApiUrl = "http://localhost:8000/api/v1/csv/ingest-csv"

if (-not (Test-Path $CsvPath)) {
    Write-Host "[ERROR] Sample CSV not found: $CsvPath" -ForegroundColor Red
    exit 1
}

try {
    Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5 | Out-Null
} catch {
    Write-Host "[ERROR] Backend is not ready at http://localhost:8000" -ForegroundColor Red
    Write-Host "Start services first: docker compose up -d" -ForegroundColor Yellow
    exit 1
}

Write-Host "[INFO] Importing sample jobs from $CsvPath"
Write-Host "[INFO] This may take a few minutes. Avoid repeated searches while importing."

curl.exe -X POST $ApiUrl `
  -F "file=@$CsvPath" `
  -F "index_to_elasticsearch=true" `
  -F "create_neo4j_nodes=true" `
  -F "process_with_nlp=false" `
  -F "batch_size=100"

Write-Host ""
Write-Host "[OK] Import request submitted."
Write-Host "Check Elasticsearch count: http://localhost:9200/jobs/_count"
