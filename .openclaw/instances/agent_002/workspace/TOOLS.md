<!-- Managed by openclaw-podman-starter: persona scaffold -->
# TOOLS.md - つむぎ 用のローカルメモ

## Runtime Snapshot

- Instance: 2
- Pod: `openclaw-2-pod`
- Container: `openclaw-2`
- Model: `zai/glm-5.1`
- Gateway: `http://127.0.0.1:18791/`
- Bridge: `http://127.0.0.1:18792/`
- Workspace: `D:\Prj\openclaw-podman-starter\.openclaw\instances\agent_002\workspace`
- Config dir: `D:\Prj\openclaw-podman-starter\.openclaw\instances\agent_002`
- Mattermost lounge scripts: `/home/node/.openclaw/mattermost-tools`

## 実務メモ

- Python は `uv` を使う
- Instance init: `./scripts/init.ps1 --instance 2`
- Dry-run launch: `./scripts/launch.ps1 --instance 2 --dry-run`
- Logs: `./scripts/logs.ps1 --instance 2 -Follow`

## この file の用途

これは つむぎ 用の cheat sheet です。環境固有の事実はここへ置き、
共有 skill prompt には混ぜないでください。
