param(
    [string]$MachineName = "podman-machine-default",
    [int]$Count = 3,
    [switch]$PreferPodmanDesktop = $true
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$reportDir = Join-Path $repoRoot "reports"
$logPath = Join-Path $reportDir "autostart-last.log"

New-Item -ItemType Directory -Path $reportDir -Force | Out-Null

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
    Write-Output $line
}

function Invoke-Step {
    param(
        [string]$Label,
        [string]$FilePath,
        [string[]]$ArgumentList
    )

    Write-Log "START $Label"
    $output = & $FilePath @ArgumentList 2>&1
    $exitCode = $LASTEXITCODE
    if ($output) {
        $output | ForEach-Object { Write-Log "$Label :: $_" }
    }
    if ($exitCode -ne 0) {
        throw "$Label failed with exit code $exitCode"
    }
    Write-Log "DONE $Label"
}

function Wait-Until {
    param(
        [scriptblock]$Condition,
        [int]$TimeoutSeconds = 60,
        [int]$SleepMilliseconds = 1000,
        [string]$Label = "condition"
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Condition) {
            return $true
        }
        Start-Sleep -Milliseconds $SleepMilliseconds
    }
    throw "Timed out waiting for $Label"
}

$uv = (Get-Command uv -ErrorAction Stop).Source
$podman = (Get-Command podman -ErrorAction Stop).Source
$podmanDesktop = Join-Path $env:LOCALAPPDATA "Programs\Podman Desktop\Podman Desktop.exe"

Write-Log "autostart bootstrap begin"
Write-Log "repoRoot=$repoRoot"
Write-Log "uv=$uv"
Write-Log "podman=$podman"
Write-Log "podmanDesktop=$podmanDesktop"

if ($PreferPodmanDesktop -and (Test-Path $podmanDesktop)) {
    $desktopRunning = @(Get-Process -Name "Podman Desktop" -ErrorAction SilentlyContinue).Count -gt 0
    Write-Log "podmanDesktopRunning=$desktopRunning"
    if (-not $desktopRunning) {
        Write-Log "starting Podman Desktop"
        Start-Process -FilePath $podmanDesktop -WindowStyle Minimized | Out-Null
    }
    Wait-Until -Label "Podman Desktop process" -TimeoutSeconds 45 -Condition {
        @(Get-Process -Name "Podman Desktop" -ErrorAction SilentlyContinue).Count -gt 0
    } | Out-Null
}

$machineState = "missing"
try {
    $inspectJson = & $podman machine inspect $MachineName 2>$null | Out-String
    if ($LASTEXITCODE -eq 0 -and $inspectJson.Trim()) {
        $machine = ($inspectJson | ConvertFrom-Json)[0]
        if ($machine -and $machine.State) {
            $machineState = [string]$machine.State
        }
    }
} catch {
    $machineState = "missing"
}

Write-Log "machineState=$machineState"
if ($machineState -ne "running") {
    $startOutput = & $podman machine start $MachineName 2>&1
    $startExit = $LASTEXITCODE
    if ($startOutput) {
        $startOutput | ForEach-Object { Write-Log "podman machine start :: $_" }
    }
    if ($startExit -ne 0 -and -not ($startOutput -join "`n" -match "already running")) {
        throw "podman machine start failed with exit code $startExit"
    }
}

Wait-Until -Label "podman machine running" -TimeoutSeconds 90 -Condition {
    try {
        $inspectJson = & $podman machine inspect $MachineName 2>$null | Out-String
        if ($LASTEXITCODE -ne 0 -or -not $inspectJson.Trim()) {
            return $false
        }
        $machine = ($inspectJson | ConvertFrom-Json)[0]
        return $machine -and [string]$machine.State -eq "running"
    } catch {
        return $false
    }
} | Out-Null

Invoke-Step -Label "launch" -FilePath $uv -ArgumentList @("run", "--project", $repoRoot, "openclaw-podman", "launch", "--count", "$Count")

$statusOutput = & $uv run --project $repoRoot openclaw-podman autochat status --count $Count 2>&1
$statusExit = $LASTEXITCODE
if ($statusOutput) {
    $statusOutput | ForEach-Object { Write-Log "autochat status :: $_" }
}
if ($statusExit -ne 0) {
    Write-Log "autochat status indicates missing jobs; enabling autochat"
    Invoke-Step -Label "autochat-enable" -FilePath $uv -ArgumentList @("run", "--project", $repoRoot, "openclaw-podman", "autochat", "enable", "--count", "$Count")
}

Invoke-Step -Label "boardview" -FilePath $uv -ArgumentList @("run", "--project", $repoRoot, "openclaw-podman", "boardview", "--thread", "background-lounge")

$finalStatus = & $uv run --project $repoRoot openclaw-podman status --count $Count 2>&1
if ($finalStatus) {
    $finalStatus | ForEach-Object { Write-Log "final status :: $_" }
}
Write-Log "autostart bootstrap complete"
