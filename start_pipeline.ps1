# start_pipeline.ps1 — atalho de uso diário para subir o ComfyUI
# Roda o ComfyUI em modo medvram, abre o browser no UI dele em http://localhost:8188

[CmdletBinding()]
param(
    [int]$Port = 8188,
    [ValidateSet('lowvram', 'medvram', 'normalvram', 'highvram')]
    [string]$VramMode = 'medvram',
    [switch]$NoBrowser,
    [switch]$Background
)
$ErrorActionPreference = 'Stop'

$ProjectRoot = $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
$ComfyMain = Join-Path $ProjectRoot 'ComfyUI\main.py'

if (-not (Test-Path $VenvPython)) {
    Write-Host "venv não encontrada. Rode setup.ps1 primeiro." -ForegroundColor Red
    exit 1
}

$args = @($ComfyMain, '--port', $Port, "--$VramMode", '--preview-method', 'auto')
if ($NoBrowser) { $args += '--disable-auto-launch' }

if ($Background) {
    $log = Join-Path $ProjectRoot 'logs\comfyui_runtime.log'
    $proc = Start-Process -FilePath $VenvPython -ArgumentList $args -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError "$log.err"
    Write-Host "ComfyUI iniciado em background. PID=$($proc.Id). Log: $log" -ForegroundColor Green
    Write-Host "Para encerrar: Stop-Process -Id $($proc.Id)" -ForegroundColor Yellow
    $proc.Id | Set-Content (Join-Path $ProjectRoot 'logs\comfyui.pid')
} else {
    Write-Host "Iniciando ComfyUI em foreground (Ctrl+C para parar)..." -ForegroundColor Cyan
    Write-Host "URL: http://localhost:$Port" -ForegroundColor Green
    & $VenvPython @args
}
