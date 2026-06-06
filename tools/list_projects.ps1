# tools/list_projects.ps1 — lista projetos existentes.

[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$VenvPython = Join-Path $Root 'venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) { throw "venv nao encontrada. Rode setup.ps1." }

Push-Location $Root
try { & $VenvPython -m orchestrator.main list-projects } finally { Pop-Location }
