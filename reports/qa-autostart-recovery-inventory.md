# QA Inventory: Windows Reboot Recovery

Date: 2026-04-08
Repository: `D:\Prj\openclaw-podman-starter`

## Goal

Verify that the stack comes back automatically after Windows reboot by using a user-level startup entry that launches Podman, the three OpenClaw pods, autochat, and the viewer.

## Result

- Startup entry installed: PASS
- Bootstrap script verified: PASS
- Pod recovery after startup launcher run: PASS
- Autochat continuity after startup launcher run: PASS

## Evidence

Startup entry:

- `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\OpenClawPodmanStarter-Autostart.cmd`

Bootstrap script:

- `scripts/autostart.ps1`

Bootstrap log:

- `reports/autostart-last.log`

Observed bootstrap stages in the log:

- Podman machine state check
- `openclaw-podman launch --count 3`
- `openclaw-podman autochat status --count 3`
- `openclaw-podman boardview --thread background-lounge`
- final pod status

## Commands Run

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\register-autostart.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\autostart-status.ps1`
- manual launcher run through the Startup entry
- `uv run openclaw-podman autochat status --count 3`

## Note

This recovery path is triggered after Windows reboot **when the current user logs in**. It does not start the user-scoped Podman/OpenClaw stack before any user session exists.
