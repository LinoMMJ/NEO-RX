param(
    [switch]$SkipTests,
    [switch]$SkipModel,
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$testTemp = Join-Path $projectRoot ('.preflight-temp/' + [guid]::NewGuid().ToString('N'))
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
$previousColors = $env:DJANGO_COLORS

function Invoke-CheckedStep {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Host "`n==> $Name" -ForegroundColor Cyan
    $global:LASTEXITCODE = 0
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Name falló con código $LASTEXITCODE."
    }
}

New-Item -ItemType Directory -Force -Path $testTemp | Out-Null
$env:TEMP = $testTemp
$env:TMP = $testTemp
$env:DJANGO_COLORS = 'nocolor'

Push-Location $projectRoot
try {
    Set-Location $backendRoot
    Invoke-CheckedStep 'Django: configuración' { & $Python manage.py check }
    Invoke-CheckedStep 'Django: cambios sin migración' { & $Python manage.py makemigrations --check --dry-run }
    Invoke-CheckedStep 'Django: migraciones aplicadas' { & $Python manage.py migrate --check }

    if (-not $SkipTests) {
        Invoke-CheckedStep 'Backend: pruebas completas' {
            & $Python -m pytest -q --basetemp (Join-Path $testTemp 'pytest') --junitxml (Join-Path $testTemp 'backend.xml')
        }
    }

    if (-not $SkipModel) {
        Invoke-CheckedStep 'Flujo local aislado: JWT, CNN real, imagen, informe, PDF y DICOM SR' {
            & $Python (Join-Path $PSScriptRoot 'smoke_local.py')
        }
    }
    Set-Location $frontendRoot
    if (-not $SkipTests) {
        Invoke-CheckedStep 'Frontend: pruebas y contraste' { npm.cmd test }
    }
    Invoke-CheckedStep 'Frontend: análisis estático' { npm.cmd run lint }
    Invoke-CheckedStep 'Frontend: build de producción' { npm.cmd run build }
    Write-Host "`nVerificación local completada, sin Docker. Evidencias: $testTemp" -ForegroundColor Green
    Write-Host 'Esto verifica funcionamiento de software, no exactitud ni aptitud clínica del modelo.'
    if ($SkipTests -or $SkipModel) { Write-Warning 'Verificación parcial: se omitieron pruebas mediante los parámetros.' }
}
finally {
    Pop-Location
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
    $env:DJANGO_COLORS = $previousColors
    # Keep the unique test directory for diagnosis; never delete a shared path.
}
