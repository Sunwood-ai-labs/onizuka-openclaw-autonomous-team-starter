param(
    [string]$EntryName = "OpenClawPodmanStarter-Autostart.cmd"
)

$ErrorActionPreference = "Stop"
$startupDir = [Environment]::GetFolderPath("Startup")
$entryPath = Join-Path $startupDir $EntryName

if (Test-Path $entryPath) {
    Remove-Item -LiteralPath $entryPath -Force
    Write-Output "Removed startup entry: $entryPath"
} else {
    Write-Output "Startup entry not found: $entryPath"
}
