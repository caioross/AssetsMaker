# 03_install_python_env.ps1
# Cria venv local e instala todas as deps Python (ComfyUI + orquestrador).

[CmdletBinding()]
param([switch]$Force)
$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$PythonExe = Join-Path $ProjectRoot 'python\python.exe'
$VenvDir = Join-Path $ProjectRoot 'venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$ComfyDir = Join-Path $ProjectRoot 'ComfyUI'

if (-not (Test-Path $PythonExe)) {
    throw "Python embeddable não instalado. Rode 01_install_python.ps1 primeiro."
}
if (-not (Test-Path $ComfyDir)) {
    throw "ComfyUI não clonado. Rode 02_install_comfyui.ps1 primeiro."
}

if ((Test-Path $VenvPython) -and -not $Force) {
    Write-Host "venv já existe em $VenvDir. Use -Force para recriar." -ForegroundColor Green
} else {
    if (Test-Path $VenvDir) {
        Write-Host "Removendo venv anterior..." -ForegroundColor Yellow
        Remove-Item -Path $VenvDir -Recurse -Force
    }
    Write-Host "Instalando virtualenv no Python embeddable..."
    & $PythonExe -m pip install --no-warn-script-location virtualenv
    Write-Host "Criando venv em $VenvDir..."
    & $PythonExe -m virtualenv $VenvDir
    if (-not (Test-Path $VenvPython)) { throw "Falha ao criar venv" }
}

# Upgrade pip
& $VenvPython -m pip install --upgrade pip wheel setuptools

# PyTorch com CUDA — versão fixa, testada com ComfyUI atual
Write-Host ""
Write-Host "Instalando PyTorch + CUDA 12.4 (download grande, ~3GB)..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Dependências do ComfyUI
$comfyReqs = Join-Path $ComfyDir 'requirements.txt'
if (Test-Path $comfyReqs) {
    Write-Host ""
    Write-Host "Instalando requirements do ComfyUI..." -ForegroundColor Cyan
    & $VenvPython -m pip install -r $comfyReqs
}

# Dependências do orquestrador
Write-Host ""
Write-Host "Instalando dependências do orquestrador..." -ForegroundColor Cyan
$orchestratorReqs = Join-Path $ProjectRoot 'orchestrator\requirements.txt'
if (Test-Path $orchestratorReqs) {
    & $VenvPython -m pip install -r $orchestratorReqs
} else {
    # Fallback: instala explícito
    & $VenvPython -m pip install `
        'pydantic>=2.5' `
        'pyyaml>=6.0' `
        'requests>=2.31' `
        'websocket-client>=1.7' `
        'pillow>=10.0' `
        'numpy>=1.26' `
        'scikit-learn>=1.3' `
        'tqdm>=4.66' `
        'rich>=13.7' `
        'typer>=0.9' `
        'rembg[gpu]>=2.0.50' `
        'onnxruntime-gpu>=1.16'
}

# Verificação CUDA disponível
Write-Host ""
Write-Host "Verificando CUDA..." -ForegroundColor Cyan
$cudaCheck = & $VenvPython -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
Write-Host $cudaCheck -ForegroundColor Green

if ($cudaCheck -notmatch 'CUDA available: True') {
    Write-Host "AVISO: CUDA não detectado. Verifique driver NVIDIA e tente novamente." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Ambiente virtual instalado: $VenvDir" -ForegroundColor Green
