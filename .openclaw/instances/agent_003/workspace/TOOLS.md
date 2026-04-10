<!-- Managed by openclaw-podman-starter: persona scaffold -->
# TOOLS.md - さく 用のローカルメモ

## Runtime Snapshot

- Instance: 3
- Pod: `openclaw-3-pod`
- Container: `openclaw-3`
- Model: `zai/glm-5.1`
- Gateway: `http://127.0.0.1:18793/`
- Bridge: `http://127.0.0.1:18794/`
- Workspace: `D:\Prj\openclaw-podman-starter\.openclaw\instances\agent_003\workspace`
- Config dir: `D:\Prj\openclaw-podman-starter\.openclaw\instances\agent_003`
- Mattermost lounge scripts: `/home/node/.openclaw/mattermost-tools`

## 実務メモ

- Python は `uv` を使う
- Instance init: `./scripts/init.ps1 --instance 3`
- Dry-run launch: `./scripts/launch.ps1 --instance 3 --dry-run`
- Logs: `./scripts/logs.ps1 --instance 3 -Follow`

## この file の役割

これは さく 用の cheat sheet です。環境固有の事実はここへ置き、
共有 skill prompt には混ぜないでください。
