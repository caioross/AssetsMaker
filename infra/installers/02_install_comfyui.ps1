# 02_install_comfyui.ps1
# Clona ComfyUI dentro da pasta do projeto e prepara para usar o Python local.

[CmdletBinding()]
param([switch]$Force)
$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ComfyDir = Join-Path $ProjectRoot 'ComfyUI'
$ComfyRepo = 'https://github.com/comfyanonymous/ComfyUI.git'

if ((Test-Path (Join-Path $ComfyDir 'main.py')) -and -not $Force) {
    Write-Host "ComfyUI já clonado em $ComfyDir. Use -Force para refazer." -ForegroundColor Green
    Push-Location $ComfyDir
    try {
        Write-Host "Atualizando para latest..."
        git pull
    } finally { Pop-Location }
    exit 0
}

if (Test-Path $ComfyDir) {
    Write-Host "Removendo instalação anterior do ComfyUI..." -ForegroundColor Yellow
    Remove-Item -Path $ComfyDir -Recurse -Force
}

Write-Host "Clonando ComfyUI de $ComfyRepo..."
git clone --depth=1 $ComfyRepo $ComfyDir
if ($LASTEXITCODE -ne 0) { throw "git clone falhou" }

# Estrutura adicional necessária
$dirs = @(
    'models\checkpoints',
    'models\controlnet',
    'models\clip_vision',
    'models\ipadapter',
    'models\loras',
    'models\upscale_models',
    'models\vae',
    'custom_nodes',
    'input',
    'output',
    'temp'
)
foreach ($d in $dirs) {
    $full = Join-Path $ComfyDir $d
    if (-not (Test-Path $full)) {
        New-Item -ItemType Directory -Path $full -Force | Out-Null
    }
}

# Cria script de start dedicado que usa o Python local + venv
$startScript = @'
# start_comfyui.ps1 — inicia o servidor ComfyUI usando o ambiente local
[CmdletBinding()]
param(
    [int]$Port = 8188,
    [string]$VramMode = 'medvram',   # lowvram | medvram | normalvram | highvram
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$VenvPython = Join-Path $Root 'venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) { throw "venv não criada. Rode setup.ps1 primeiro." }

$ComfyMain = Join-Path $Root 'ComfyUI\main.py'
$vramFlag = "--$VramMode"
$args = @($ComfyMain, '--port', $Port, $vramFlag, '--preview-method', 'auto')
if ($NoBrowser) { $args += '--disable-auto-launch' }

Write-Host "Iniciando ComfyUI em http://localhost:$Port (vram=$VramMode)..."
& $VenvPython @args
'@

$startPath = Join-Path $ComfyDir 'start_comfyui.ps1'
Set-Content -Path $startPath -Value $startScript -Encoding UTF8

Write-Host ""
Write-Host "ComfyUI instalado em $ComfyDir" -ForegroundColor Green
Write-Host "Para iniciar: $startPath" -ForegroundColor Green
