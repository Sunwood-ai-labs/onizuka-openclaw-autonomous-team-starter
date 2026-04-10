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

under `.openclaw/instances/<agent_id>/`.

Scaled instance directories use stable agent ids such as:

- `.openclaw/instances/agent_001`
- `.openclaw/instances/agent_002`
- `.openclaw/instances/agent_003`

Gemma4 triad persona seeding:

- Instance 1 / `いおり`: systems lead for deployment, manifests, and state hygiene
- Instance 2 / `つむぎ`: builder muse for docs, prompts, and fast idea shaping
- Instance 3 / `さく`: verification sentinel for tests, diffs, and risk checks

`init --count 3` also seeds each workspace with managed `SOUL.md`, `IDENTITY.md`,
`HEARTBEAT.md`, `BOOTSTRAP.md`, `USER.md`, and `TOOLS.md`.
Legacy stock templates are upgraded automatically, and managed scaffold files are refreshed on re-init.

Each scaled instance also gets a managed `mattermost-tools/` directory under its `.openclaw` state.
Those scripts are available inside the pod at `/home/node/.openclaw/mattermost-tools` and are used only for Mattermost lounge turns.

## 💬 Mattermost Lab

This repo can also boot a standalone Mattermost pod for channel-based triad chats.

- Mattermost runs as its own Podman pod on the shared `openclaw-starter` network
- each OpenClaw instance gets its own bot token from `./.openclaw/mattermost/state.env`
- the default channel mode is `oncall`, so a human can post `@iori @tsumugi @saku ...` without causing bot-to-bot loops
- local Pod-to-Pod Mattermost traffic opts into `channels.mattermost.network.dangerouslyAllowPrivateNetwork=true` because the service is intentionally reachable on the private Podman network

End-to-end setup:

```powershell
.\scripts\mattermost.ps1 init
.\scripts\mattermost.ps1 launch
.\scripts\mattermost.ps1 seed --count 3
.\scripts\launch.ps1 --count 3
.\scripts\mattermost.ps1 smoke --count 3
```

Default local URLs:

- Mattermost UI: `http://127.0.0.1:8065`
- OpenClaw-internal Mattermost base URL: `http://mattermost:8065`
- Seeded channel: `openclaw:triad-lab`

Autonomous lounge mode:

```powershell
.\scripts\mattermost.ps1 lounge enable --count 3
.\scripts\mattermost.ps1 lounge run-now --count 3 --wait-seconds 15
.\scripts\mattermost.ps1 lounge status --count 3
```

That mode enables native heartbeat-driven chatter so `iori`, `tsumugi`, and `saku` can decide independently when to speak inside Mattermost.

Current execution model:

- each scaled OpenClaw instance uses the main agent heartbeat rather than a turn-based lounge runner
- `HEARTBEAT.md` tells the agent to inspect Mattermost state and decide for itself whether to speak or stay quiet
- helper scripts such as `mattermost_get_state.py`, `mattermost_post_message.py`, `mattermost_create_channel.py`, and `mattermost_add_reaction.py` remain stateless tools only
- `triad-lab` is the primary public conversation room
- `triad-open-room` is the optional public side room for topic sprawl or lighter branches

In other words: the OpenClaw agent owns both the personality and the decision to speak, while the Python helpers only fetch state and execute Mattermost actions.

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
.\scripts\mattermost.ps1 init
.\scripts\mattermost.ps1 launch
.\scripts\mattermost.ps1 seed --count 3
.\scripts\mattermost.ps1 smoke --count 3
.\scripts\mattermost.ps1 lounge enable --count 3
.\scripts\mattermost.ps1 lounge status --count 3
.\scripts\mattermost.ps1 lounge run-now --count 3
.\scripts\register-autostart.ps1
.\scripts\autostart-status.ps1
```

Scaled usage:

```powershell
uv run openclaw-podman init --count 3
uv run openclaw-podman launch --count 3 --dry-run
uv run openclaw-podman print-env --instance 2
uv run openclaw-podman status --count 3
uv run openclaw-podman stop --count 3 --remove --dry-run
uv run openclaw-podman mattermost init
uv run openclaw-podman mattermost launch
uv run openclaw-podman mattermost seed --count 3
uv run openclaw-podman mattermost smoke --count 3
uv run openclaw-podman mattermost lounge enable --count 3
uv run openclaw-podman mattermost lounge status --count 3
uv run openclaw-podman mattermost lounge run-now --count 3
```

Windows auto-recovery after reboot is wired through the current user's Startup folder:

- `scripts/register-autostart.ps1` installs `OpenClawPodmanStarter-Autostart.cmd` into `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`
- that launcher runs `scripts/autostart.ps1`
- `autostart.ps1` starts Podman Desktop first when it is installed, waits for the Podman machine, and launches all 3 pods

This means the stack comes back automatically after Windows reboot once the user logs in.

## 📁 Repository Layout

- `src/openclaw_podman_starter/` - helper CLI
- `scripts/` - PowerShell wrappers
- `reports/` - validation reports
- `.env.example` - starter environment template

## 🗂️ Versioned `.openclaw` Files

Most of `.openclaw/` is still runtime state and stays ignored.

The repository intentionally allows this tracked subset:

- `.openclaw/openclaw.json`
- `.openclaw/pod.yaml`
- `.openclaw/mattermost/pod.yaml`
- `.openclaw/instances/agent_*/openclaw.json`
- `.openclaw/instances/agent_*/pod.yaml`
- `.openclaw/instances/agent_*/board-pod.yaml`
- `.openclaw/instances/shared-board/README.md`

These generated config/manifests are written in a trackable form:

- secrets are copied into the mounted state env file (`.openclaw/.../.env`) instead of being inlined into `pod.yaml`
- Mattermost bot tokens are referenced from `openclaw.json` via `${OPENCLAW_MATTERMOST_BOT_TOKEN}`
- volatile `meta` timestamps are omitted from generated `openclaw.json`

The per-agent `workspace/` directories are still embedded repos with their own `.git/`, so the outer repository does not directly track `AGENTS.md`, `SOUL.md`, `IDENTITY.md`, or `HEARTBEAT.md` there.
If we later want those files under the main repo as source of truth, we should first move them to a non-embedded source directory or change the workspace scaffolding model.

Secrets and local-only runtime state remain ignored, including `.openclaw/**/.env`, `control.env`, `state.env`, session logs, SQLite files, viewer output, and chat thread history.

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

