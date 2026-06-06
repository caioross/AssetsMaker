# setup.ps1 — Orquestrador mestre de instalação do SISTEMA AssetsMaker
# Roda todos os passos em ordem, com logging e parada limpa em caso de erro.

[CmdletBinding()]
param(
    [switch]$SkipModels,    # Pula download de modelos (útil para debug)
    [switch]$SkipVerify,    # Pula smoke test final
    [switch]$Force          # Refaz etapas mesmo se já parecerem instaladas
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$LogDir = Join-Path $ProjectRoot 'logs'
$Timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$LogFile = Join-Path $LogDir "setup_$Timestamp.log"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

function Write-Step {
    param([string]$Msg, [string]$Color = 'Cyan')
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $Msg"
    Write-Host $line -ForegroundColor $Color
    Add-Content -Path $LogFile -Value $line
}

function Invoke-Installer {
    param([string]$Script, [string]$Label)
    Write-Step "==> $Label" 'Yellow'
    $path = Join-Path $ProjectRoot "infra\installers\$Script"
    if (-not (Test-Path $path)) {
        throw "Installer não encontrado: $path"
    }
    $args = @()
    if ($Force) { $args += '-Force' }
    & $path @args
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne $null) {
        throw "Installer falhou: $Script (exit $LASTEXITCODE)"
    }
    Write-Step "    OK: $Label" 'Green'
}

Write-Step "================================================================" 'Magenta'
Write-Step "SISTEMA AssetsMaker — Setup" 'Magenta'
Write-Step "Pasta: $ProjectRoot" 'Magenta'
Write-Step "Log:   $LogFile" 'Magenta'
Write-Step "================================================================" 'Magenta'

# Pré-requisitos rápidos
Write-Step "Checando pré-requisitos..."
$gitOk = $null -ne (Get-Command git -ErrorAction SilentlyContinue)
if (-not $gitOk) {
    throw "Git não encontrado no PATH. Instale Git for Windows: https://git-scm.com/download/win"
}
Write-Step "    OK: git encontrado" 'Green'

# Verifica GPU NVIDIA via nvidia-smi (não-fatal, só avisa)
$nvSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($nvSmi) {
    $gpuInfo = & nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>&1
    Write-Step "    GPU: $gpuInfo" 'Green'
} else {
    Write-Step "    AVISO: nvidia-smi não encontrado. GPU NVIDIA é necessária para o ComfyUI." 'Yellow'
}

# Etapas
try {
    Invoke-Installer '01_install_python.ps1'           'Python 3.11 embeddable'
    Invoke-Installer '02_install_comfyui.ps1'          'ComfyUI (clone + config)'
    Invoke-Installer '03_install_python_env.ps1'       'Ambiente virtual + dependências'
    Invoke-Installer '04_install_comfy_extensions.ps1' 'Custom nodes ComfyUI'

    if (-not $SkipModels) {
        Invoke-Installer '05_download_models.ps1'      'Download de modelos (pode demorar)'
    } else {
        Write-Step "==> PULANDO: download de modelos (--SkipModels)" 'Yellow'
    }

    if (-not $SkipVerify) {
        Invoke-Installer '06_verify_install.ps1'       'Smoke test (geração de 1 imagem)'
    } else {
        Write-Step "==> PULANDO: smoke test (--SkipVerify)" 'Yellow'
    }
} catch {
    Write-Step "ERRO: $_" 'Red'
    Write-Step "Log completo: $LogFile" 'Red'
    exit 1
}

Write-Step "================================================================" 'Green'
Write-Step "SETUP COMPLETO" 'Green'
Write-Step "================================================================" 'Green'
Write-Step "Próximos passos:" 'White'
Write-Step "  1. Leia USAGE.md" 'White'
Write-Step "  2. Para iniciar o ComfyUI:  .\start_pipeline.ps1" 'White'
Write-Step "  3. Para abrir no Claude Code:  claude" 'White'
Write-Step "" 'White'
Write-Step "Log: $LogFile" 'Gray'
