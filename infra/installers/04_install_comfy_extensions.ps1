# 04_install_comfy_extensions.ps1
# Instala custom nodes essenciais no ComfyUI (clonando como submodule-like).

[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$Update
)
$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ComfyDir = Join-Path $ProjectRoot 'ComfyUI'
$CustomNodesDir = Join-Path $ComfyDir 'custom_nodes'
$ManifestPath = Join-Path $ProjectRoot 'infra\extensions_manifest.json'
$VenvPython = Join-Path $ProjectRoot 'venv\Scripts\python.exe'

if (-not (Test-Path $ComfyDir)) {
    throw "ComfyUI não encontrado. Rode 02_install_comfyui.ps1 primeiro."
}
if (-not (Test-Path $ManifestPath)) {
    throw "Manifesto não encontrado: $ManifestPath"
}

$manifest = Get-Content -Path $ManifestPath -Raw | ConvertFrom-Json

foreach ($ext in $manifest.extensions) {
    $name = $ext.name
    $url = $ext.url
    $target = Join-Path $CustomNodesDir $name

    Write-Host ""
    Write-Host "→ $name" -ForegroundColor Cyan

    if (Test-Path $target) {
        if ($Update) {
            Write-Host "   atualizando..."
            Push-Location $target
            try { git pull } finally { Pop-Location }
        } elseif ($Force) {
            Write-Host "   removendo (Force)..."
            Remove-Item -Path $target -Recurse -Force
        } else {
            Write-Host "   já instalado, pulando" -ForegroundColor Green
            continue
        }
    }

    if (-not (Test-Path $target)) {
        Write-Host "   clonando de $url..."
        git clone --depth=1 $url $target
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Falha ao clonar $name. Continuando."
            continue
        }
    }

    # Roda requirements.txt do custom node se existir
    $extReqs = Join-Path $target 'requirements.txt'
    if (Test-Path $extReqs) {
        Write-Host "   instalando requirements..."
        & $VenvPython -m pip install -r $extReqs --no-warn-script-location
    }

    Write-Host "   OK" -ForegroundColor Green
}

Write-Host ""
Write-Host "Extensões instaladas em: $CustomNodesDir" -ForegroundColor Green
