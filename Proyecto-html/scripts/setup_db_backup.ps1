<#
  `setup_db_backup.ps1` - Crea una tarea programada diaria que ejecuta
  `scripts/backup_db.py` usando el Python de la carpeta `.venv` si existe,
  o `python` del PATH en caso contrario.

  Ejecutar con PowerShell (como usuario):
    .\scripts\setup_db_backup.ps1 -Time "02:00"

#>
param(
    [string]$Time = "02:00",
    [string]$TaskName = "SENNOVA_DB_Backup"
)

Set-StrictMode -Version Latest

# Determine project root (donde está este script)
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
$projectRoot = Resolve-Path "$scriptPath/.."

# Buscar python en .venv/Scripts
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (Test-Path $venvPython) {
    $pythonExe = $venvPython
} else {
    $pythonExe = 'python'
}

$backupScript = Join-Path $projectRoot 'scripts\backup_db.py'
if (-not (Test-Path $backupScript)) {
    Write-Error "No se encontró $backupScript"
    exit 1
}

# Crear la tarea programada para el usuario actual
$action = "`"$pythonExe`" `"$backupScript`""
Write-Host "Creando tarea programada '$TaskName' que ejecuta: $action a las $Time"

schtasks /Create /SC DAILY /TN $TaskName /TR $action /ST $Time /F | Out-Host

Write-Host "Tarea creada (si falla con permisos, ejecuta PowerShell como administrador)." 
