param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Continue"
$Repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$LogPath = Join-Path $Repo "ml\api_server_$Port.log"
Set-Location $Repo
$env:PYTHONPATH = Join-Path $Repo "ml\src"

"Starting ML API at http://127.0.0.1:$Port $(Get-Date -Format s)" | Set-Content -Path $LogPath -Encoding UTF8
$Command = "python -m uvicorn ml_service.api:app --host 127.0.0.1 --port $Port >> `"$LogPath`" 2>&1"
cmd.exe /c $Command
