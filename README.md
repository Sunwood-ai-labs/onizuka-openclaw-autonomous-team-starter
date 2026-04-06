<div align="center">

# openclaw-podman-multi-pod-starter

![Project header](./assets/header.svg)

Run OpenClaw inside Podman with file-based `podman kube play` manifests, isolated multi-instance state, and validated local-model setups for Ollama Gemma and Z.AI GLM.

[日本語 README](./README.ja.md)

![CI](https://github.com/Sunwood-ai-labs/openclaw-podman-multi-pod-starter/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/github/license/Sunwood-ai-labs/openclaw-podman-multi-pod-starter)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Podman](https://img.shields.io/badge/podman-kube%20play-892CA0)

[Docs Site](https://sunwood-ai-labs.github.io/openclaw-podman-multi-pod-starter/)

</div>

## ✨ Overview

This repository packages a practical Windows-first starter for running OpenClaw in Podman.

Key ideas:

- One instance = one Podman pod = one OpenClaw gateway container
- Instance state, workspace, token, and ports are isolated
- Runtime manifests are generated as `pod.yaml` files and executed with `podman kube play`
- The repo can scale to multiple independent local instances such as 3 side-by-side pods
- Validation reports for `zai/glm-5-turbo`, `ollama/gemma4:e4b`, and `ollama/gemma4:e2b` are included

## 🧭 Why This Repo Exists

OpenClaw's official docs explain Podman and multi-gateway concepts, but operating several local instances with repeatable manifests, Windows path handling, and local-model verification still takes glue work.

This repo provides that glue:

- a small Python CLI managed by `uv`
- PowerShell wrappers for common operations
- generated per-instance state and manifests
- known-good verification notes for pod-local agent execution

## 🚀 Quick Start

```powershell
cd D:\Prj\openclaw-podman-multi-pod-starter
uv sync
Copy-Item .env.example .env
notepad .env
.\scripts\init.ps1
.\scripts\doctor.ps1
.\scripts\launch.ps1 --dry-run
```

Generated files for the single-instance path:

- `.openclaw/openclaw.json`
- `.openclaw/.env`
- `.openclaw/pod.yaml`

Actual runtime command:

```powershell
podman kube play --replace --no-pod-prefix .\.openclaw\pod.yaml
```

## 🧱 Scale Out

Launch 3 isolated local instances:

```powershell
.\scripts\init.ps1 --count 3
.\scripts\launch.ps1 --count 3 --dry-run
.\scripts\status.ps1 --count 3
.\scripts\logs.ps1 --instance 2 -Follow
.\scripts\stop.ps1 --count 3 --remove
```

Default topology:

- Instance 1: `openclaw-1-pod` on `127.0.0.1:18789`
- Instance 2: `openclaw-2-pod` on `127.0.0.1:18791`
- Instance 3: `openclaw-3-pod` on `127.0.0.1:18793`

Each instance gets its own:

- `control.env`
- `.env`
- `openclaw.json`
- `pod.yaml`
- `workspace/`

under `.openclaw/instances/<N>/`.

Gemma4 triad persona seeding:

- Instance 1 / `Aster`: systems lead for deployment, manifests, and state hygiene
- Instance 2 / `Lyra`: builder muse for docs, prompts, and fast idea shaping
- Instance 3 / `Noctis`: verification sentinel for tests, diffs, and risk checks

`init --count 3` also seeds each workspace with managed `SOUL.md`, `IDENTITY.md`,
`HEARTBEAT.md`, `BOOTSTRAP.md`, `USER.md`, and `TOOLS.md`.
Legacy stock templates are upgraded automatically, and managed scaffold files are refreshed on re-init.

## ⚙️ Model Setups

### Ollama

Default starter values:

- model: `ollama/gemma4:e2b`
- base URL: `http://host.containers.internal:11434`

On the actual Windows + WSL Podman machine used for validation, the working host-side Ollama endpoint was:

```text
http://172.27.208.1:11434
```

If `host.containers.internal` does not reach your Windows-hosted Ollama instance, replace `OPENCLAW_OLLAMA_BASE_URL` in `.env`.

### Z.AI

Verified Z.AI path:

- model: `zai/glm-5-turbo`

The repo can pass `ZAI_API_KEY` through to the pod when present in `.env`.

## ✅ Verification Reports

Validation notes are kept in:

- [GLM-5-Turbo pod report](./reports/pod-openclaw-glm5-turbo-report.md)
- [Gemma pod report](./reports/pod-openclaw-gemma-report.md)

Those reports document:

- pod-local health checks
- agent-side file generation and execution
- transcript-backed `write` / `read` / `exec` evidence

## 🛠️ Main Commands

```powershell
.\scripts\init.ps1
.\scripts\launch.ps1
.\scripts\status.ps1
.\scripts\logs.ps1 -Follow
.\scripts\stop.ps1 --remove
.\scripts\print-env.ps1
```

Scaled usage:

```powershell
uv run openclaw-podman init --count 3
uv run openclaw-podman launch --count 3 --dry-run
uv run openclaw-podman print-env --instance 2
uv run openclaw-podman status --count 3
uv run openclaw-podman stop --count 3 --remove --dry-run
```

## 📁 Repository Layout

- `src/openclaw_podman_starter/` - helper CLI
- `scripts/` - PowerShell wrappers
- `reports/` - validation reports
- `.env.example` - starter environment template

## 🔐 Trust Model

This repo is designed for same-trust operator workflows.

It isolates instances operationally, but it is not intended to claim hard multi-tenant security separation. OpenClaw is configured in a full-access-in-container mode and relies on the outer Podman boundary rather than OpenClaw's internal sandbox.

## 🧪 CI

The included GitHub Actions workflow validates:

- `uv sync`
- Python source compilation
- helper CLI help output
- single-instance init
- multi-instance dry-run generation

## 📚 References

- [OpenClaw Podman docs](https://docs.openclaw.ai/install/podman)
- [OpenClaw Multiple Gateways](https://docs.openclaw.ai/gateway/multiple-gateways)
- [OpenClaw Ollama provider docs](https://docs.openclaw.ai/providers/ollama)
- [OpenClaw local models guidance](https://docs.openclaw.ai/gateway/local-models)
- [Podman kube play](https://docs.podman.io/en/latest/markdown/podman-kube-play.1.html)
- [Podman kube down](https://docs.podman.io/en/latest/markdown/podman-kube-down.1.html)
- [Ollama OpenClaw integration](https://docs.ollama.com/integrations/openclaw)
