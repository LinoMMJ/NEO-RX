param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$EnvironmentFile = Join-Path $ProjectRoot '.env.docker'
if ((Test-Path -LiteralPath $EnvironmentFile) -and -not $Force) {
    Write-Host ".env.docker ya existe. Usa -Force únicamente si deseas regenerar sus secretos."
    exit 0
}

function New-RandomBytes([int]$Length) {
    $bytes = [byte[]]::new($Length)
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    return $bytes
}

function New-HexSecret([int]$Length = 48) {
    return ([BitConverter]::ToString((New-RandomBytes $Length))).Replace('-', '').ToLowerInvariant()
}

function New-FernetKey {
    $value = [Convert]::ToBase64String((New-RandomBytes 32))
    return $value.Replace('+', '-').Replace('/', '_')
}

$lines = @(
    "SECRET_KEY=$(New-HexSecret 48)",
    "FERNET_KEY=$(New-FernetKey)",
    'POSTGRES_DB=neorx',
    'POSTGRES_USER=neorx',
    "POSTGRES_PASSWORD=$(New-HexSecret 24)",
    '',
    'ALLOWED_HOSTS=localhost,127.0.0.1',
    'CORS_ALLOWED_ORIGINS=http://localhost:8080',
    'SECURE_SSL_REDIRECT=False',
    'SECURE_HSTS_SECONDS=0',
    'NEORX_HTTP_PORT=8080',
    '',
    'NEORX_INPUT_SIZE=512',
    'NEORX_TORCH_THREADS=4',
    'NEORX_CNN_SOFT_LIMIT=180',
    'NEORX_CNN_TIME_LIMIT=240',
    '',
    '# Vacío: usa ResNet-50 preentrenado y lo almacena en backend/models.',
    'NEORX_MODEL_PATH=',
    'NEORX_BASELINE_WEIGHTS=resnet50-res512-all',
    'NEORX_DECISION_MODE=pretrained_effusion_categories',
    'NEORX_BASELINE_MIN_SCORE=0.50',
    'NEORX_CATEGORY_MARGIN=0.00',
    'NEORX_DEMO_ORIENTATION=false',
    '',
    'NEORX_CREATE_DEMO_USERS=true',
    'NEORX_ADMIN_PASSWORD=Admin123!',
    'NEORX_MEDICO_PASSWORD=Medico123!',
    'NEORX_RECEPCIONISTA_PASSWORD=Recepcionista123!'
)
[IO.File]::WriteAllLines($EnvironmentFile, $lines, [Text.UTF8Encoding]::new($false))
New-Item -ItemType Directory -Force (Join-Path $ProjectRoot 'logs') | Out-Null

Write-Host "Configuración Docker creada: $EnvironmentFile"
Write-Host 'Acceso local: http://localhost:8080'
Write-Host 'Usuarios demo: admin / medico / recepcionista'
Write-Host 'Contraseñas demo: Admin123! / Medico123! / Recepcionista123!'
Write-Warning 'Estas credenciales son solo para una demostración local. No las uses en producción.'
