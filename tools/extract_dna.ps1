# tools/extract_dna.ps1 — extrai o partial DNA das referencias de um projeto.

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Project,
    [string]$Output
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$VenvPython = Join-Path $Root 'venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) { throw "venv nao encontrada. Rode setup.ps1." }

$args = @('-m', 'orchestrator.main', 'extract-dna', $Project)
if ($Output) { $args += '--output'; $args += $Output }

Push-Location $Root
try { & $VenvPython @args } finally { Pop-Location }
