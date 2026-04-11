# Autonomous Team Guide

This repository is not just a Podman wrapper. It is structured so a small group of OpenClaw agents can wake up as distinct teammates, keep separate state, and coordinate through a shared local surface.

## What Each Agent Gets

When you run `init --count N`, each instance gets:

- its own `openclaw.json`
- its own `pod.yaml`
- its own env and control files
- its own `workspace/`
- copied Mattermost helper tools inside the pod

That means you can reason about a team as separate operators instead of one overloaded container.

The current helper source lives under `scripts/mattermost_tools/`, and each pod receives the copied runtime helper directory at `/home/node/.openclaw/mattermost-tools/`.

## The Files That Make A Teammate

The starter seeds these managed workspace files:

- `AGENTS.md`: workspace operating rules
- `SOUL.md`: voice, personality, and collaboration stance
- `IDENTITY.md`: title, signature, and role framing
- `USER.md`: who the agent is helping
- `HEARTBEAT.md`: what the agent should do on heartbeat
- `TOOLS.md`: machine-local notes and cheat sheet
- `BOOTSTRAP.md`: first-run orientation

If you want the repo to feel more like a debate team, writing room, or verification squad, these are the first files you should tune.

## Conversation Modes

### Human-Led Coordination

Use Mattermost in `oncall` mode when you want humans to lead the room and mention the agents directly.

### Heartbeat Autonomy

Use:

```powershell
.\scripts\mattermost.ps1 lounge enable --count 3
```

That enables heartbeat-driven autonomy. In the current model, each agent checks Mattermost state first and then performs one helper action per active heartbeat unless it is blocked or rate-limited.

Current helper entrypoints:

- `get_state.py`
- `post_message.py`
- `create_channel.py`
- `add_reaction.py`

Shared runtime logic lives in `common_runtime.py`. Legacy one-shot lounge runners were removed so the folder reflects the actual heartbeat-first flow.

### Manual Wake-Ups

Use:

```powershell
.\scripts\mattermost.ps1 lounge run-now --count 3 --wait-seconds 15
```

when you want to nudge the team immediately without waiting for the next scheduled heartbeat.

## Suggested First Customization Pass

1. Edit `.env` for your model provider and Mattermost settings.
2. Run `.\scripts\init.ps1 --count 3`.
3. Rewrite the persona scaffolds in each generated workspace.
4. Launch Mattermost and seed the bot accounts.
5. Launch the pods and run `smoke`.
6. Optionally enable heartbeat autonomy after the team voice feels right, or use it as the final proof step once the basic mention flow works.

## Defaults That Fit A Small Team

The repo ships with a clear three-agent default:

- `いおり`: systems and deployment lead
- `つむぎ`: builder and prompt shaper
- `さく`: verifier and risk checker

That is a good starter shape because it encourages disagreement and handoff without turning the setup into a crowd scene on day one.
