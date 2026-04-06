# Quick Start

## Prerequisites

- `uv`
- `Podman`
- `openclaw` CLI
- `ollama` CLI
- A local Ollama model such as `gemma4:e2b`

## Single Instance

```powershell
cd D:\Prj\openclaw-podman-multi-pod-starter
uv sync
Copy-Item .env.example .env
notepad .env
.\scripts\init.ps1
.\scripts\doctor.ps1
.\scripts\launch.ps1 --dry-run
```

Runtime command:

```powershell
podman kube play --replace --no-pod-prefix .\.openclaw\pod.yaml
```

## Three Instances

```powershell
.\scripts\init.ps1 --count 3
.\scripts\launch.ps1 --count 3 --dry-run
.\scripts\status.ps1 --count 3
.\scripts\logs.ps1 --instance 2 -Follow
.\scripts\stop.ps1 --count 3 --remove
```

Default ports:

- Instance 1: `127.0.0.1:18789`
- Instance 2: `127.0.0.1:18791`
- Instance 3: `127.0.0.1:18793`

Default Gemma4 triad personas:

- Instance 1 / `Aster`: systems lead
- Instance 2 / `Lyra`: builder muse
- Instance 3 / `Noctis`: verification sentinel

`init --count 3` seeds each instance workspace with managed `SOUL.md`, `IDENTITY.md`,
`HEARTBEAT.md`, `BOOTSTRAP.md`, `USER.md`, and `TOOLS.md`.
