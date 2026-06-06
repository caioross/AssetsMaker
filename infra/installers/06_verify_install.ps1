# 06_verify_install.ps1
# Sobe ComfyUI temporariamente, gera 1 imagem via REST, mata o processo, valida o PNG.

[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$VenvPython = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
$ComfyMain = Join-Path $ProjectRoot 'ComfyUI\main.py'
$TestOutDir = Join-Path $ProjectRoot 'test_outputs'
if (-not (Test-Path $TestOutDir)) { New-Item -ItemType Directory -Path $TestOutDir | Out-Null }

if (-not (Test-Path $VenvPython)) { throw "venv não encontrada. Rode setup.ps1." }
if (-not (Test-Path $ComfyMain)) { throw "ComfyUI não encontrado." }

# Inicia ComfyUI em background
Write-Host "Iniciando ComfyUI em background na porta 8188..."
$comfyArgs = @($ComfyMain, '--port', '8188', '--medvram', '--disable-auto-launch')
$proc = Start-Process -FilePath $VenvPython -ArgumentList $comfyArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $ProjectRoot 'logs\comfy_smoketest.log') -RedirectStandardError (Join-Path $ProjectRoot 'logs\comfy_smoketest.err.log')
Start-Sleep -Seconds 5

# Aguarda ComfyUI responder
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8188/system_stats' -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 2
}

if (-not $ready) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    throw "ComfyUI não respondeu em 60s. Veja logs\comfy_smoketest.log"
}

Write-Host "ComfyUI online. Rodando teste do orquestrador..." -ForegroundColor Green

try {
    $smokePy = Join-Path $ProjectRoot 'orchestrator\smoke_test.py'
    & $VenvPython $smokePy
    if ($LASTEXITCODE -ne 0) { throw "smoke_test.py retornou $LASTEXITCODE" }
} finally {
    Write-Host ""
    Write-Host "Encerrando ComfyUI..."
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Smoke test OK." -ForegroundColor Green
