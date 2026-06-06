# 05_download_models.ps1
# Baixa todos os modelos listados em models_manifest.json para ComfyUI/models/.
# Idempotente: pula o que já existe e tem o tamanho correto.

[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$OnlyMissing,
    [string[]]$Category  # Filtra por categoria (checkpoint, controlnet, ipadapter, lora, vae, upscaler)
)
$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ComfyModels = Join-Path $ProjectRoot 'ComfyUI\models'
$ManifestPath = Join-Path $ProjectRoot 'infra\models_manifest.json'

if (-not (Test-Path $ManifestPath)) { throw "Manifesto não encontrado: $ManifestPath" }
$manifest = Get-Content -Path $ManifestPath -Raw | ConvertFrom-Json

# Função de download com progresso e retry
function Invoke-ModelDownload {
    param(
        [string]$Url,
        [string]$Destination,
        [string]$Token = $null,
        [long]$ExpectedSize = 0,
        [int]$MaxRetries = 3
    )

    if ((Test-Path $Destination)) {
        $existingSize = (Get-Item $Destination).Length
        if ($ExpectedSize -gt 0 -and [math]::Abs($existingSize - $ExpectedSize) -lt 1024) {
            return $true
        }
        if ($ExpectedSize -eq 0 -and $existingSize -gt 1024) {
            return $true
        }
        if (-not $Force) {
            Write-Host "    arquivo existente parcial ($existingSize bytes); refazendo download"
            Remove-Item -Path $Destination -Force
        }
    }

    $destDir = Split-Path -Parent $Destination
    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }

    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        try {
            $headers = @{}
            if ($Token) { $headers['Authorization'] = "Bearer $Token" }
            # Usa BITS para grandes (suporta resume e mostra progresso)
            if ($ExpectedSize -gt 50MB -or $ExpectedSize -eq 0) {
                Start-BitsTransfer -Source $Url -Destination $Destination -DisplayName (Split-Path -Leaf $Destination) -ErrorAction Stop
            } else {
                Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing -Headers $headers
            }
            return $true
        } catch {
            Write-Warning "    tentativa $attempt falhou: $_"
            if ($attempt -eq $MaxRetries) { throw }
            Start-Sleep -Seconds (3 * $attempt)
        }
    }
    return $false
}

$total = $manifest.models.Count
$idx = 0
$skipped = 0
$downloaded = 0
$failed = @()

foreach ($model in $manifest.models) {
    $idx++
    if ($Category -and ($model.category -notin $Category)) { continue }

    $relPath = $model.destination -replace '/', '\'
    $destFull = Join-Path $ComfyModels $relPath

    Write-Host ""
    Write-Host "[$idx/$total] $($model.name) ($($model.category))" -ForegroundColor Cyan
    Write-Host "    URL: $($model.url)" -ForegroundColor Gray
    Write-Host "    -> $destFull" -ForegroundColor Gray

    if ((Test-Path $destFull) -and -not $Force) {
        $sz = (Get-Item $destFull).Length
        Write-Host "    OK (já presente, $([math]::Round($sz/1MB,1)) MB)" -ForegroundColor Green
        $skipped++
        continue
    }

    try {
        Invoke-ModelDownload -Url $model.url -Destination $destFull -ExpectedSize $model.size_bytes
        Write-Host "    OK" -ForegroundColor Green
        $downloaded++
    } catch {
        Write-Warning "    FALHA: $_"
        $failed += $model.name
        if ($model.required) {
            Write-Host "    Este modelo é marcado como REQUIRED. Você pode tentar baixar manualmente depois." -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "================================================================"
Write-Host "Download concluído: $downloaded baixados, $skipped pulados (já existentes)" -ForegroundColor Green
if ($failed.Count -gt 0) {
    Write-Host "Falharam:" -ForegroundColor Yellow
    $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    Write-Host ""
    Write-Host "Tente novamente:  .\infra\installers\05_download_models.ps1 -OnlyMissing" -ForegroundColor Yellow
}
