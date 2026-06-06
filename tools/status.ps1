# tools/status.ps1 — mostra resumo de um projeto.

[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Project)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$VenvPython = Join-Path $Root 'venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) { throw "venv nao encontrada. Rode setup.ps1." }

Push-Location $Root
try { & $VenvPython -m orchestrator.main status $Project } finally { Pop-Location }
