<!-- Managed by openclaw-podman-starter: persona scaffold -->
# TOOLS.md - いおり 用のローカルメモ

## Runtime Snapshot

- Instance: 1
- Pod: `openclaw-1-pod`
- Container: `openclaw-1`
- Model: `zai/glm-5.1`
- Gateway: `http://127.0.0.1:18789/`
- Bridge: `http://127.0.0.1:18790/`
- Workspace: `D:\Prj\openclaw-podman-starter\.openclaw\instances\agent_001\workspace`
- Config dir: `D:\Prj\openclaw-podman-starter\.openclaw\instances\agent_001`
- Mattermost lounge scripts: `/home/node/.openclaw/mattermost-tools`

## 実務メモ

- Python は `uv` を使う
- Instance init: `./scripts/init.ps1 --instance 1`
- Dry-run launch: `./scripts/launch.ps1 --instance 1 --dry-run`
- Logs: `./scripts/logs.ps1 --instance 1 -Follow`

## この file の用途

これは いおり 用の cheat sheet です。環境固有の事実はここへ置き、
共有 skill prompt には混ぜないでください。
