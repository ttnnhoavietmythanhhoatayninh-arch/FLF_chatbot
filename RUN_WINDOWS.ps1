param(
    [Parameter(Mandatory=$true)][string]$DataDir,
    [string]$OutputDir = '.\output',
    [ValidateSet('hybrid','llm','offline')][string]$Solver = 'hybrid'
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$InputPath = (Resolve-Path $DataDir).Path
if (-not (Test-Path (Join-Path $InputPath 'queries.json'))) { throw 'DataDir must contain queries.json' }
if (-not (Test-Path (Join-Path $InputPath 'xlsx_files'))) { throw 'DataDir must contain xlsx_files' }
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$ResultPath = (Resolve-Path $OutputDir).Path
if ($InputPath -eq $ResultPath -or $ResultPath.StartsWith($InputPath.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Output must be outside the input folder' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install Docker Desktop, start it and select Linux containers first.' }
$OriginalKey = $env:OPENROUTER_API_KEY
try {
    if ($Solver -ne 'offline' -and -not $env:OPENROUTER_API_KEY) {
        $SecureKey = Read-Host 'OpenRouter API key (hidden input)' -AsSecureString
        $KeyPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
        try { $env:OPENROUTER_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($KeyPtr) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($KeyPtr) }
    }
    docker build --platform linux/amd64 -t excelqa2026:local .
    if ($LASTEXITCODE -ne 0) { throw 'Docker build failed. Do not submit yet.' }
    docker run --rm --platform linux/amd64 --memory=4g --cpus=6 `
        --read-only --tmpfs '/tmp:rw,size=64m' `
        --mount "type=bind,source=$InputPath,target=/input,readonly" `
        --mount "type=bind,source=$ResultPath,target=/output" `
        -e OPENROUTER_API_KEY excelqa2026:local `
        --xlsx-dir /input/xlsx_files --queries /input/queries.json `
        --output /output/submission.csv `
        --openrouter-model qwen/qwen3.7-flash `
        --openrouter-base-url https://openrouter.ai/api/v1 `
        --solver $Solver --report /output/run_report.json
    if ($LASTEXITCODE -ne 0) { throw 'Run incomplete. Inspect errors and run_report.json; CSV may contain unanswered rows.' }
    Write-Host "Completed: $ResultPath\submission.csv"
}
finally { $env:OPENROUTER_API_KEY = $OriginalKey }
