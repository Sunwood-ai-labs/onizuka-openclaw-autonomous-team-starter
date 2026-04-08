param(
    [string]$EntryName = "OpenClawPodmanStarter-Autostart.cmd",
    [string]$MachineName = "podman-machine-default",
    [int]$Count = 3
)

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "autostart.ps1"
$startupDir = [Environment]::GetFolderPath("Startup")
$entryPath = Join-Path $startupDir $EntryName
$powershellExe = (Get-Command powershell -ErrorAction Stop).Source

$launcher = @"
@echo off
start "" /min "$powershellExe" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$scriptPath" -MachineName "$MachineName" -Count $Count
"@

Set-Content -LiteralPath $entryPath -Value $launcher -Encoding ASCII

[pscustomobject]@{
    StartupDir = $startupDir
    EntryPath = $entryPath
    Exists = Test-Path $entryPath
} | Format-List
