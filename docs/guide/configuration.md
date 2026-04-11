# Configuration

## Core Environment Variables

- `OPENCLAW_IMAGE`: OpenClaw image to run
- `OPENCLAW_PODMAN_PUBLISH_HOST`: host publish address
- `OPENCLAW_OLLAMA_BASE_URL`: Ollama native API URL
- `OPENCLAW_OLLAMA_MODEL`: default Ollama model id
- `OPENCLAW_SCALE_INSTANCE_ROOT`: root directory for generated instances
- `OPENCLAW_SCALE_GATEWAY_PORT_START`: first gateway port
- `OPENCLAW_SCALE_BRIDGE_PORT_START`: first bridge port
- `OPENCLAW_SCALE_PORT_STEP`: per-instance port increment

## Agent-Team Tuning

These env vars control the communication lab:

- `OPENCLAW_MATTERMOST_ENABLED`
- `OPENCLAW_MATTERMOST_CHANNEL_NAME`
- `OPENCLAW_MATTERMOST_AUTONOMY_ENABLED`
- `OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL`
- `OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL_INSTANCE_00N`
- `OPENCLAW_MATTERMOST_AUTONOMY_MODEL`

Most team behavior still lives in the workspace scaffolds rather than env vars. Use `.env` for infrastructure defaults, then tune `SOUL.md`, `IDENTITY.md`, `USER.md`, and `HEARTBEAT.md` inside each generated workspace.

## Important Note For Windows + WSL Podman

The working Ollama endpoint observed during validation was:

```text
http://172.27.208.1:11434
```

If `host.containers.internal` does not reach the Windows-hosted Ollama instance in your environment, replace `OPENCLAW_OLLAMA_BASE_URL` accordingly.

## Trust Model

This project targets same-trust operator workflows. OpenClaw is configured in a full-access-in-container mode and depends on the Podman pod boundary rather than OpenClaw's internal sandbox for the main isolation layer.
