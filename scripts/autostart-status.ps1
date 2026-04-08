param(
    [string]$EntryName = "OpenClawPodmanStarter-Autostart.cmd"
)

$ErrorActionPreference = "Stop"
$startupDir = [Environment]::GetFolderPath("Startup")
$entryPath = Join-Path $startupDir $EntryName

if (-not (Test-Path $entryPath)) {
    Write-Output "Startup entry not found: $entryPath"
    exit 1
}

[pscustomobject]@{
    StartupDir = $startupDir
    EntryPath = $entryPath
    Exists = $true
    LastWriteTime = (Get-Item -LiteralPath $entryPath).LastWriteTime
} | Format-List
