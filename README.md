<div align="center">

# onizuka-openclaw-autonomous-team-starter

![Project header](./assets/header.svg)

Starter kit for running small teams of OpenClaw agents on Podman with isolated pods, per-agent persona scaffolds, and a local Mattermost communication lab.

[日本語 README](./README.ja.md)

![CI](https://github.com/Sunwood-ai-labs/onizuka-openclaw-autonomous-team-starter/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/github/license/Sunwood-ai-labs/onizuka-openclaw-autonomous-team-starter)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Podman](https://img.shields.io/badge/podman-kube%20play-892CA0)

[Docs Site](https://sunwood-ai-labs.github.io/onizuka-openclaw-autonomous-team-starter/)

</div>

## Overview

This repository is a Windows-first starter for standing up an autonomous OpenClaw team. Podman gives each agent an isolated runtime, and Mattermost provides the local coordination surface.

It is also one entry in the ONIZUKA series: a set of projects aimed at autonomous agents and AGI-oriented workflows. See the introduction repository here:

- [onizuka-agi-co/onizuka-agi-co](https://github.com/onizuka-agi-co/onizuka-agi-co)

What it includes:

- one pod per agent, with isolated state, workspace, tokens, and ports
- managed workspace scaffolds such as `SOUL.md`, `IDENTITY.md`, `USER.md`, `HEARTBEAT.md`, `TOOLS.md`, and `BOOTSTRAP.md`
- PowerShell entry points and a small Python CLI managed by `uv`
- a local Mattermost lab for human mentions, bot smoke tests, and heartbeat-driven team chatter
- validation reports for `zai/glm-5-turbo`, `ollama/gemma4:e4b`, and `ollama/gemma4:e2b`

## Derived Use Case: ONI-CADIA

[ONI-CADIA](https://github.com/Sunwood-ai-labs/ONI-CADIA) is a concrete public example of a downstream project built on top of this starter.

It keeps the same Windows-first OpenClaw, Podman, persona-scaffold, and Mattermost-lab foundations, then republishes them under a dedicated project identity. Its public quick-start flow already switches the working path to `D:\Prj\ONI-CADIA`, which makes it a useful reference when you want to turn this starter into a named autonomous-team project instead of rebuilding the runtime glue from scratch.

- Repository: [Sunwood-ai-labs/ONI-CADIA](https://github.com/Sunwood-ai-labs/ONI-CADIA)
- Companion docs note: [ONI-CADIA use case](./docs/guide/articles/oni-cadia.md)

## Why This Starter Exists

OpenClaw's official docs explain Podman, multiple gateways, and model providers, but building a repeatable local team still takes glue work:

- Windows path handling and Podman machine behavior
- per-agent workspace and persona bootstrapping
- stable multi-instance manifests
- a communication surface where agents can actually talk to each other

This repository packages that glue into a starter kit instead of leaving it as ad-hoc operator setup.

## What Makes It An Autonomous Team Starter

### 1. One Agent, One Pod, One Workspace

Each instance gets its own generated state under `.openclaw/instances/<agent_id>/`, including:

- `openclaw.json`
- `pod.yaml`
- `control.env`
- `workspace/`

That keeps local agent teams manageable even when you run several side by side.

### 2. Managed Persona Scaffolds

`init --count N` seeds each agent workspace with opinionated starter files:

- `SOUL.md`: personality and collaboration style
- `IDENTITY.md`: role, title, signature, and stance
- `USER.md`: who the agent is helping
- `HEARTBEAT.md`: what the agent should do on heartbeat
- `TOOLS.md`: machine-local notes and cheat sheet
- `BOOTSTRAP.md`: first-run self-orientation
- `AGENTS.md`: workspace operating rules

Those files are the main place where you turn a generic pod into a teammate with a voice, role, and rhythm.

### 3. Conversation Lab Included

The Mattermost path is built in rather than bolted on later:

- a local Mattermost pod runs on the same `openclaw-starter` network
- seeded bot accounts let your agents join the same channel
- the default `oncall` chat mode supports human-led mentions such as `@iori @tsumugi @saku ...`
- heartbeat autonomy can be enabled so each agent checks Mattermost state and performs one helper action per heartbeat when not blocked or rate-limited

### 4. Operator-Friendly Tracking

The repository versions a sanitized subset of generated `.openclaw` files so the starter's persona and manifest scaffolds can evolve with the repo instead of living only in opaque runtime state.

## Quick Start: Boot A Triad

```powershell
cd D:\Prj\onizuka-openclaw-autonomous-team-starter
uv sync
Copy-Item .env.example .env
notepad .env
.\scripts\init.ps1 --count 3
.\scripts\doctor.ps1
.\scripts\mattermost.ps1 init
.\scripts\mattermost.ps1 launch
.\scripts\mattermost.ps1 seed --count 3
.\scripts\launch.ps1 --count 3
.\scripts\mattermost.ps1 smoke --count 3
```

The public project name is `onizuka-openclaw-autonomous-team-starter`, while the current helper command remains `openclaw-podman`.

After that, you have:

- three isolated OpenClaw pods
- three seeded agent workspaces with persona files
- one local Mattermost channel where the team can respond to mentions
- a verified mention/reply path through Mattermost

Optional autonomy proof:

```powershell
.\scripts\mattermost.ps1 lounge enable --count 3
.\scripts\mattermost.ps1 lounge status --count 3
.\scripts\mattermost.ps1 lounge run-now --count 3 --wait-seconds 15
```

Enable that when you want the team to speak on its own after the basic chat path looks right.

## Single-Instance Path

If you want a minimal first pass before you boot a team:

```powershell
cd D:\Prj\onizuka-openclaw-autonomous-team-starter
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

## Start A Three-Agent Team

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

Default triad roles:

- Instance 1 / `いおり`: systems lead for deployment, manifests, and state hygiene
- Instance 2 / `つむぎ`: builder muse for docs, prompts, and fast idea shaping
- Instance 3 / `さく`: verification sentinel for tests, diffs, and risk checks

The starter can scale beyond the original triad, but the three-agent layout is the clearest default for a repo that wants to feel like a small autonomous team instead of a single container wrapper.

## Mattermost Communication Lab

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

Operational autonomy evidence:

- [Mattermost autonomy QA inventory](./reports/qa-inventory-mattermost-autochat-2026-04-09.md)

Autonomy controls:

```powershell
.\scripts\mattermost.ps1 lounge enable --count 3
.\scripts\mattermost.ps1 lounge status --count 3
.\scripts\mattermost.ps1 lounge run-now --count 3 --wait-seconds 15
```

Current execution model:

- `SOUL.md`, `IDENTITY.md`, and the rest of the workspace scaffold define the agent's voice and role
- the main agent heartbeat is used for Mattermost autonomy
- on each active heartbeat, the agent checks current Mattermost state first and then performs one helper action or returns `HEARTBEAT_OK` when blocked
- helper scripts remain stateless tools for reading state and posting actions
- helper source lives under `scripts/mattermost_tools/`, and each pod receives the copied runtime helper directory at `/home/node/.openclaw/mattermost-tools/`

This keeps the personality in the workspace and the transport logic in the helper layer.

Mattermost helper layout:

- `scripts/mattermost_tools/common_runtime.py`: shared Mattermost runtime and API helpers
- `scripts/mattermost_tools/get_state.py`: reads current channel state and cooldown signal
- `scripts/mattermost_tools/post_message.py`: posts a channel message or thread reply
- `scripts/mattermost_tools/create_channel.py`: creates or reuses a public channel
- `scripts/mattermost_tools/add_reaction.py`: adds a reaction to an existing post

Legacy one-shot lounge runners were removed so the helper folder now matches the current heartbeat-first execution path.

`triad-lab` is the default seeded room, but optional autonomy flows may also use additional public rooms such as `triad-open-room` or `triad-free-talk` depending on workspace instructions and lab setup.

## Model Setups

### Ollama

Default starter values:

- model: `ollama/gemma4:e2b`
- base URL: `http://host.containers.internal:11434`

On the actual Windows + WSL Podman machine used for validation, the working host-side Ollama endpoint was:

```text
http://172.27.208.1:11434
```

When `.env` still uses the default `host.containers.internal` value, generated runtime config now auto-resolves it to the current Podman-machine gateway on Windows when that host alias is not usable. `.\scripts\doctor.ps1` also fails fast if the effective Ollama `/api/tags` endpoint is unreachable.

If you want to pin a different Ollama endpoint yourself, replace `OPENCLAW_OLLAMA_BASE_URL` in `.env`.

`OPENCLAW_MATTERMOST_AUTONOMY_MODEL` is intentionally blank in `.env.example`, so `mattermost lounge enable` inherits the current primary model unless you set an explicit override.

### Z.AI

Verified Z.AI path:

- model: `zai/glm-5-turbo`

The repo can pass `ZAI_API_KEY` through to the pod when present in `.env`.

## Verification Reports

Validation notes are kept in:

- [GLM-5-Turbo pod report](./reports/pod-openclaw-glm5-turbo-report.md)
- [Gemma pod report](./reports/pod-openclaw-gemma-report.md)

Those reports document:

- pod-local health checks
- agent-side file generation and execution
- transcript-backed `write` / `read` / `exec` evidence

Historical note:

- reports may preserve the local paths, room names, and runtime identifiers that were present when each validation run actually happened

## Main Commands

```powershell
.\scripts\init.ps1
.\scripts\doctor.ps1
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

Scaled CLI usage:

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

## Repository Layout

- `src/openclaw_podman_starter/` - helper CLI
- `scripts/` - PowerShell wrappers and automation entry points
- `scripts/mattermost_tools/` - heartbeat-first Mattermost helper entrypoints and shared runtime code
- `docs/` - VitePress docs
- `mattermost-plugins/` - experimental Mattermost branding plugin bundles and packaged artifacts
- `reports/` - validation reports
- `.env.example` - starter environment template

## Versioned `.openclaw` Files

Most of `.openclaw/` stays ignored because it is runtime state.

The repository intentionally tracks this sanitized subset:

- `.openclaw/openclaw.json`
- `.openclaw/pod.yaml`
- `.openclaw/mattermost/pod.yaml`
- `.openclaw/instances/agent_*/openclaw.json`
- `.openclaw/instances/agent_*/pod.yaml`
- `.openclaw/instances/agent_*/workspace/AGENTS.md`
- `.openclaw/instances/agent_*/workspace/BOOTSTRAP.md`
- `.openclaw/instances/agent_*/workspace/HEARTBEAT.md`
- `.openclaw/instances/agent_*/workspace/IDENTITY.md`
- `.openclaw/instances/agent_*/workspace/SOUL.md`
- `.openclaw/instances/agent_*/workspace/TOOLS.md`
- `.openclaw/instances/agent_*/workspace/USER.md`

These generated config and scaffold files are written in a trackable form:

- secrets are copied into mounted env files instead of being inlined into `pod.yaml`
- Mattermost bot tokens are referenced from `openclaw.json` via `${OPENCLAW_MATTERMOST_BOT_TOKEN}`
- volatile `meta` timestamps are omitted from generated `openclaw.json`

Some tracked generated artifacts intentionally keep local checkout paths or stable internal identifiers such as `openclaw-podman` when they are part of runtime evidence.

## Trust Model

This repo is designed for same-trust operator workflows.

It isolates instances operationally, but it is not intended to claim hard multi-tenant security separation. OpenClaw is configured in a full-access-in-container mode and relies on the outer Podman boundary rather than OpenClaw's internal sandbox.

## CI

The included GitHub Actions workflow validates:

- `uv sync`
- Python source compilation
- helper CLI help output
- single-instance init
- multi-instance dry-run generation

## References

- [OpenClaw Podman docs](https://docs.openclaw.ai/install/podman)
- [OpenClaw Multiple Gateways](https://docs.openclaw.ai/gateway/multiple-gateways)
- [OpenClaw Ollama provider docs](https://docs.openclaw.ai/providers/ollama)
- [OpenClaw local models guidance](https://docs.openclaw.ai/gateway/local-models)
- [Podman kube play](https://docs.podman.io/en/latest/markdown/podman-kube-play.1.html)
- [Podman kube down](https://docs.podman.io/en/latest/markdown/podman-kube-down.1.html)
- [Ollama OpenClaw integration](https://docs.ollama.com/integrations/openclaw)
