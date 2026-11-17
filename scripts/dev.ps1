# School ERP development launcher for Windows PowerShell.
#
# Best-effort equivalent of scripts/dev.sh. It prefers Docker when a daemon is
# reachable and otherwise runs the documented SQLite fallback. Background
# processes are tracked in data/dev.pids and `down` only stops those it started.
#
# Limits compared with dev.sh:
#   * Requires PowerShell 5.1+ and an existing uv/pnpm install (no auto-install).
#   * Logs are written as <name>.log and <name>.err; `logs` tails both.
#   * Process-tree cleanup uses taskkill /T, which is Windows-specific.
param(
  [Parameter(Position = 0)]
  [ValidateSet("up", "seed", "reset", "test", "mobile", "logs", "down", "help")]
  [string]$Command = "help"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$DataDir = Join-Path $Root "data"
$LogDir = Join-Path $DataDir "logs"
$PidFile = Join-Path $DataDir "dev.pids"
$ComposeFile = Join-Path $Root "deploy\compose\dev.yml"
$ComposeMarker = Join-Path $DataDir "dev.compose"
New-Item -ItemType Directory -Force -Path $DataDir, $LogDir | Out-Null

function Write-Dev([string]$Message) { Write-Host "[dev] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "[dev] $Message" -ForegroundColor Yellow }
function Write-Err([string]$Message) { Write-Host "[dev] $Message" -ForegroundColor Red }
function Write-Step([string]$Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }

function Resolve-Python {
  $candidates = @()
  if ($env:ERP_PYTHON) { $candidates += $env:ERP_PYTHON }
  $candidates += (Join-Path $Root ".venv\Scripts\python.exe")
  $candidates += (Join-Path $Root "school-erp\backend\.venv\Scripts\python.exe")
  $candidates += "python"
  foreach ($candidate in $candidates) {
    if (-not $candidate) { continue }
    try {
      $path = (Get-Command $candidate -ErrorAction Stop).Source
      & $path -c "import fastapi, sqlalchemy, uvicorn, aiosqlite" 2>$null
      if ($LASTEXITCODE -eq 0) { return $path }
    } catch { }
  }
  throw "No Python with backend dependencies. Run 'uv sync --all-packages' or set ERP_PYTHON."
}

function Resolve-Pnpm {
  $cmd = Get-Command pnpm -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  throw "pnpm was not found on PATH."
}

function Test-Docker {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
  & docker info *> $null
  return $LASTEXITCODE -eq 0
}

function Get-ProcessStart([int]$ProcessId) {
  try { return (Get-Process -Id $ProcessId -ErrorAction Stop).StartTime.ToFileTime() } catch { return $null }
}

function Get-Tracked {
  if (-not (Test-Path $PidFile)) { return @() }
  $rows = @()
  foreach ($line in Get-Content $PidFile) {
    $parts = $line -split "`t"
    if ($parts.Count -ge 4) {
      $rows += [pscustomobject]@{ Name = $parts[0]; Id = [int]$parts[1]; Port = $parts[2]; Start = $parts[3] }
    }
  }
  return $rows
}

function Save-Tracked($Rows) {
  $lines = @($Rows | ForEach-Object { "{0}`t{1}`t{2}`t{3}" -f $_.Name, $_.Id, $_.Port, $_.Start })
  if ($lines.Count -eq 0) {
    if (Test-Path $PidFile) { Remove-Item -Force $PidFile }
  } else {
    $lines | Set-Content -Path $PidFile -Encoding ascii
  }
}

function Remove-Tracked($Rows, [string]$Name) {
  return @($Rows | Where-Object { $_.Name -ne $Name })
}

function Start-DevProcess([string]$Name, [string]$Port, [string]$WorkDir, [string]$FilePath, [string[]]$Arguments) {
  $rows = @(Get-Tracked)
  $existing = $rows | Where-Object { $_.Name -eq $Name } | Select-Object -First 1
  if ($existing -and (Get-Process -Id $existing.Id -ErrorAction SilentlyContinue)) {
    Write-Dev "$Name already running (pid $($existing.Id))"
    return
  }
  $rows = Remove-Tracked $rows $Name
  Save-Tracked $rows

  if ($Port -ne "-") {
    $busy = Get-NetTCPConnection -LocalPort ([int]$Port) -State Listen -ErrorAction SilentlyContinue
    if ($busy) { Write-Warn "$Name`: port $Port is already in use; not starting it"; return }
  }

  $outLog = Join-Path $LogDir "$Name.log"
  $errLog = Join-Path $LogDir "$Name.err"
  Write-Dev "starting $Name (port $Port)"
  $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $WorkDir `
    -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru -WindowStyle Hidden
  Start-Sleep -Milliseconds 500
  if (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) {
    $rows += [pscustomobject]@{ Name = $Name; Id = $process.Id; Port = $Port; Start = (Get-ProcessStart $process.Id) }
    Save-Tracked $rows
    Write-Dev "$Name started (pid $($process.Id)); logs data/logs/$Name.log"
  } else {
    Write-Err "$Name failed to start; see data/logs/$Name.err"
    if (Test-Path $errLog) { Get-Content $errLog -Tail 20 }
  }
}

function Wait-Health([string]$Url, [int]$TimeoutSeconds = 60) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2 -ErrorAction Stop
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) { return $true }
    } catch { }
    Start-Sleep -Milliseconds 500
  }
  return $false
}

function Set-DevEnvironment([bool]$UseCompose) {
  $env:APP_ENV = if ($env:APP_ENV) { $env:APP_ENV } else { "development" }
  $env:DEV_MODE = "true"
  $env:SECRET_KEY = "dev-only-change-me-please-0123456789abcdef"
  $env:REFRESH_SECRET = "dev-only-change-me-too-0123456789abcdef"
  $env:CONTROLLER_SECRET_KEY = "controller-dev-only-change-me-0123456789"
  # Dev-only directory signing key; the mobile app embeds the matching public key.
  # Override in production. Existing databases keep their first key, so run
  # `scripts/dev.ps1 reset` once if the controller was seeded before.
  if (-not $env:DIRECTORY_KID) { $env:DIRECTORY_KID = "k1" }
  if (-not $env:DIRECTORY_PRIVATE_KEY) {
    $env:DIRECTORY_PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----`nMC4CAQAwBQYDK2VwBCIEICxiIR4mAY6IMg9u6c0KnMJEJIAc30HftQ7nLcOCwLDx`n-----END PRIVATE KEY-----"
  }
  $env:CORS_ORIGINS = "http://localhost:5173,http://localhost:5174,http://localhost:8081"
  $env:PUBLIC_BASE_URL = "http://localhost:8000"
  $env:CONTROLLER_URL = "http://localhost:8100"
  $env:CONTROLLER_PUBLIC_BASE_URL = "http://localhost:8100"
  $env:CONTROLLER_API_BASE_URL = "http://localhost:8100"
  $env:VITE_API_URL = "http://localhost:8000"
  $env:VITE_CONTROLLER_API_URL = "http://localhost:8100"
  $env:STORAGE_DRIVER = "local"
  $env:STORAGE_DIR = (Join-Path $DataDir "storage")
  if ($UseCompose) {
    $env:DATABASE_URL = "postgresql+psycopg://erp:erp_dev_password@localhost:5432/erp_demo"
    $env:CONTROLLER_DATABASE_URL = "postgresql+psycopg://erp:erp_dev_password@localhost:5432/controller"
    $env:REDIS_URL = "redis://localhost:6379/0"
  } else {
    $env:DATABASE_URL = "sqlite+aiosqlite:///$($DataDir.Replace('\', '/'))/erp_demo.db"
    $env:CONTROLLER_DATABASE_URL = "sqlite+aiosqlite:///$($DataDir.Replace('\', '/'))/controller.db"
  }
}

function Invoke-Up {
  $python = Resolve-Python
  $useCompose = (Test-Docker) -and (Test-Path $ComposeFile)
  Set-DevEnvironment $useCompose
  if ($useCompose) {
    Write-Step "starting docker compose services"
    & docker compose -f $ComposeFile up -d --wait
    if ($LASTEXITCODE -ne 0) {
      Write-Warn "compose failed to become healthy; using SQLite"
      $useCompose = $false
      Set-DevEnvironment $false
    } else {
      New-Item -ItemType File -Force -Path $ComposeMarker | Out-Null
    }
  } else {
    Write-Warn "Docker unavailable or compose missing: using SQLite fallback"
  }

  Write-Step "starting APIs"
  $env:PYTHONPATH = (Join-Path $Root "school-erp\backend") + ";" + (Join-Path $Root "shared\py")
  Start-DevProcess "school-api" "8000" (Join-Path $Root "school-erp\backend") $python `
    @("-m", "uvicorn", "app.entrypoint:app", "--host", "0.0.0.0", "--port", "8000")
  $env:PYTHONPATH = (Join-Path $Root "owner\controller-api") + ";" + (Join-Path $Root "shared\py")
  Start-DevProcess "controller-api" "8100" (Join-Path $Root "owner\controller-api") $python `
    @("-m", "uvicorn", "controller_api.entrypoint:app", "--host", "0.0.0.0", "--port", "8100")

  Write-Step "waiting for the APIs"
  if (Wait-Health "http://localhost:8000/health") { Write-Dev "school API is healthy" } else { Write-Err "school API did not become healthy" }
  if (Wait-Health "http://localhost:8100/health") { Write-Dev "controller API is healthy" } else { Write-Err "controller API did not become healthy" }

  try {
    $pnpm = Resolve-Pnpm
    if (Test-Path (Join-Path $Root "school-erp\web\package.json")) {
      Start-DevProcess "school-web" "5173" $Root $pnpm @("--filter", "@erp/school-web", "dev")
    }
    if (Test-Path (Join-Path $Root "owner\controller-web\package.json")) {
      Start-DevProcess "controller-web" "5174" $Root $pnpm @("--filter", "@erp/controller-web", "dev")
    }
  } catch {
    Write-Warn "pnpm unavailable; skipping web apps"
  }

  Write-Step "ready"
  Write-Host "  School API      http://localhost:8000"
  Write-Host "  Controller API  http://localhost:8100"
  Write-Host "  School web      http://localhost:5173"
  Write-Host "  Controller web  http://localhost:5174"
  Write-Host "  Logs            data/logs"
  Write-Host "  Next            .\scripts\dev.ps1 seed"
}

function Invoke-Seed {
  if ($env:APP_ENV -eq "production") { Write-Err "seed refuses to run with APP_ENV=production"; exit 2 }
  $python = Resolve-Python
  Set-DevEnvironment $false
  $env:PYTHONPATH = (Join-Path $Root "school-erp\backend") + ";" + (Join-Path $Root "owner\controller-api") + ";" + (Join-Path $Root "shared\py")
  Write-Step "seeding demo data"
  & $python (Join-Path $Root "scripts\seed.py")
  exit $LASTEXITCODE
}

function Invoke-Down {
  Write-Step "stopping dev processes"
  $rows = @(Get-Tracked)
  foreach ($row in $rows) {
    $current = Get-ProcessStart $row.Id
    if ($null -eq $current) { Write-Warn "$($row.Name) already stopped"; continue }
    if ([string]$current -ne [string]$row.Start) {
      Write-Warn "$($row.Name) pid $($row.Id) was reused; not killing it"
      continue
    }
    Write-Dev "stopping $($row.Name) (pid $($row.Id))"
    & taskkill /PID $row.Id /T /F *> $null
  }
  Remove-Item -Force -ErrorAction SilentlyContinue $PidFile
  if (Test-Path $ComposeMarker) {
    if (Test-Docker) { & docker compose -f $ComposeFile down --remove-orphans }
    Remove-Item -Force -ErrorAction SilentlyContinue $ComposeMarker
  }
}

function Invoke-Reset {
  Invoke-Down
  Write-Step "deleting local generated data"
  if (-not $DataDir.StartsWith($Root)) { throw "Refusing to delete $DataDir" }
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $DataDir
  New-Item -ItemType Directory -Force -Path $DataDir, $LogDir | Out-Null
  Invoke-Up
  Invoke-Seed
}

function Invoke-Test {
  $python = Resolve-Python
  $script:TestResults = @()
  function Run-Step([string]$Name, [scriptblock]$Action) {
    Write-Step $Name
    try {
      & $Action
      $ok = ($LASTEXITCODE -eq 0)
    } catch {
      Write-Err $_.Exception.Message
      $ok = $false
    }
    $script:TestResults += [pscustomobject]@{ Name = $Name; Ok = $ok }
  }

  $appPath = (Join-Path $Root "school-erp\backend") + ";" + (Join-Path $Root "owner\controller-api") + ";" + (Join-Path $Root "shared\py")
  $env:PYTHONPATH = $appPath
  $env:APP_ENV = "test"
  Push-Location (Join-Path $Root "school-erp\backend")
  Run-Step "school backend pytest" { & $python -m pytest }
  Pop-Location
  Push-Location (Join-Path $Root "owner\controller-api")
  Run-Step "controller pytest" { & $python -m pytest }
  Pop-Location
  Push-Location (Join-Path $Root "shared\py")
  Run-Step "shared python pytest" { & $python -m pytest }
  Pop-Location
  Push-Location $Root
  Run-Step "ruff check" { & $python -m ruff check scripts school-erp/backend owner/controller-api shared/py }
  Run-Step "import-linter" { & $python -m importlinter.cli }
  try {
    $pnpm = Resolve-Pnpm
    Run-Step "pnpm -r test" { & $pnpm -r --if-present test }
  } catch { Write-Warn "pnpm unavailable; skipping JS tests" }
  Pop-Location

  foreach ($result in $script:TestResults) {
    if ($result.Ok) { Write-Host "  PASS $($result.Name)" -ForegroundColor Green }
    else { Write-Host "  FAIL $($result.Name)" -ForegroundColor Red }
  }
  if ($script:TestResults | Where-Object { -not $_.Ok }) { exit 1 }
}

function Get-LanIp {
  try {
    $address = Get-NetIPAddress -AddressFamily IPv4 |
      Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
      Select-Object -First 1
    if ($address) { return $address.IPAddress }
  } catch { }
  return "127.0.0.1"
}

function Invoke-Mobile {
  $pnpm = Resolve-Pnpm
  if (-not (Test-Path (Join-Path $Root "owner\mobile\package.json"))) {
    Write-Err "owner/mobile/package.json is missing"; exit 1
  }
  $ip = Get-LanIp
  $env:EXPO_PUBLIC_CONTROLLER_URL = "http://$ip`:8100"
  $env:EXPO_PUBLIC_API_URL = "http://$ip`:8000"
  Write-Step "starting Expo on port 8081 (controller $($env:EXPO_PUBLIC_CONTROLLER_URL))"
  Start-DevProcess "expo" "8081" (Join-Path $Root "owner\mobile") $pnpm @("--dir", (Join-Path $Root "owner\mobile"), "exec", "expo", "start", "--lan", "--port", "8081")
}

function Invoke-Logs {
  $files = @(Get-ChildItem -Path $LogDir -Filter "*.log" -ErrorAction SilentlyContinue) +
           @(Get-ChildItem -Path $LogDir -Filter "*.err" -ErrorAction SilentlyContinue)
  if ($files.Count -eq 0) { Write-Err "no logs in $LogDir"; exit 1 }
  Write-Dev "tailing $($files.Count) log file(s); Ctrl-C to stop"
  Get-Content -Path $files.FullName -Tail 40 -Wait
}

function Show-Usage {
  @"
Usage: .\scripts\dev.ps1 <command>

  up       Start compose when Docker is available, else SQLite; then both APIs and webs.
  seed     Load demo data. Refuses APP_ENV=production.
  reset    Stop, delete local data inside the repo, then up + seed.
  test     Python/JS tests plus ruff and import-linter.
  mobile   Start Expo :8081 pointed at the LAN address.
  logs     Tail the launcher logs.
  down     Stop only the processes this script tracked (and compose if it started it).

Set ERP_PYTHON if the interpreter with backend dependencies is not in .venv.
"@
}

switch ($Command) {
  "up" { Invoke-Up }
  "seed" { Invoke-Seed }
  "reset" { Invoke-Reset }
  "test" { Invoke-Test }
  "mobile" { Invoke-Mobile }
  "logs" { Invoke-Logs }
  "down" { Invoke-Down }
  default { Show-Usage }
}
