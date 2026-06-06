# tools/new_project.ps1 — atalho para criar um novo projeto.

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Name,
    [string]$DisplayName,
    [string]$Genre = 'rts',
    [string]$Platform = 'android',
    [string]$Tone,
    [string]$Description,
    [string]$Author
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$VenvPython = Join-Path $Root 'venv\Scripts\python.exe'

if (-not (Test-Path $VenvPython)) { throw "venv nao encontrada. Rode setup.ps1 primeiro." }

$args = @('-m', 'orchestrator.main', 'new-project', $Name, '--genre', $Genre, '--platform', $Platform)
if ($DisplayName) { $args += '--display-name'; $args += $DisplayName }
if ($Tone)        { $args += '--tone'; $args += $Tone }
if ($Description) { $args += '--description'; $args += $Description }
if ($Author)      { $args += '--author'; $args += $Author }

Push-Location $Root
try {
    & $VenvPython @args
} finally {
    Pop-Location
}
