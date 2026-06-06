# 01_install_python.ps1
# Baixa Python 3.11 embeddable e configura para uso local (sem mexer no Python do sistema).

[CmdletBinding()]
param([switch]$Force)
$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$PythonDir = Join-Path $ProjectRoot 'python'
$PythonExe = Join-Path $PythonDir 'python.exe'
$PythonVersion = '3.11.9'
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$GetPipUrl = 'https://bootstrap.pypa.io/get-pip.py'

if ((Test-Path $PythonExe) -and -not $Force) {
    Write-Host "Python já instalado em $PythonDir. Use -Force para reinstalar." -ForegroundColor Green
    & $PythonExe --version
    exit 0
}

if (Test-Path $PythonDir) {
    Write-Host "Removendo instalação anterior..." -ForegroundColor Yellow
    Remove-Item -Path $PythonDir -Recurse -Force
}

New-Item -ItemType Directory -Path $PythonDir | Out-Null

# Download
$zipPath = Join-Path $env:TEMP "python-embed-$PythonVersion.zip"
Write-Host "Baixando Python $PythonVersion embeddable..."
Invoke-WebRequest -Uri $PythonUrl -OutFile $zipPath -UseBasicParsing

# Extract
Write-Host "Extraindo para $PythonDir..."
Expand-Archive -Path $zipPath -DestinationPath $PythonDir -Force
Remove-Item $zipPath

# O python embeddable vem com um arquivo python311._pth que bloqueia imports de site-packages.
# Precisamos habilitar 'import site' pra venv e pip funcionarem.
$pthFile = Get-ChildItem -Path $PythonDir -Filter 'python*._pth' | Select-Object -First 1
if ($pthFile) {
    Write-Host "Habilitando site-packages em $($pthFile.Name)..."
    $content = Get-Content $pthFile.FullName
    $content = $content -replace '#import site', 'import site'
    if (-not ($content -match '^import site$')) {
        $content += 'import site'
    }
    Set-Content -Path $pthFile.FullName -Value $content
}

# Instalar pip
Write-Host "Instalando pip..."
$getPip = Join-Path $env:TEMP 'get-pip.py'
Invoke-WebRequest -Uri $GetPipUrl -OutFile $getPip -UseBasicParsing
& $PythonExe $getPip --no-warn-script-location
Remove-Item $getPip

# Verificação
Write-Host ""
Write-Host "Python instalado:" -ForegroundColor Green
& $PythonExe --version
& $PythonExe -m pip --version

Write-Host ""
Write-Host "Path: $PythonExe" -ForegroundColor Green
