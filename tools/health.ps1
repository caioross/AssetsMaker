# tools/health.ps1 — verifica se ComfyUI esta respondendo.

[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$VenvPython = Join-Path $Root 'venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) { throw "venv nao encontrada. Rode setup.ps1." }

Push-Location $Root
try { & $VenvPython -m orchestrator.main health } finally { Pop-Location }
