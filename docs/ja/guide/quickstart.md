# クイックスタート

このページは最短でローカルチームを動かすための導線です。役割 scaffold や協働モデルを詳しく見たい時は、初回起動のあとに [自律チーム導入](/ja/guide/agent-teams) を読むと把握しやすいです。

## 前提

- `uv`
- `Podman`
- `openclaw` CLI
- OpenClaw から使える provider key、または OpenClaw から到達できるローカル Ollama model

## 3 人チームを起動

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

公開プロジェクト名: `onizuka-openclaw-autonomous-team-starter`
現行 helper command 名: `openclaw-podman`

## 生成されるもの

agent ごと:

- `.openclaw/instances/agent_00X/openclaw.json`
- `.openclaw/instances/agent_00X/pod.yaml`
- `.openclaw/instances/agent_00X/workspace/`

workspace ごと:

- `AGENTS.md`
- `SOUL.md`
- `IDENTITY.md`
- `USER.md`
- `HEARTBEAT.md`
- `TOOLS.md`
- `BOOTSTRAP.md`

## 既定の triad

- Instance 1 / `いおり`: 運用リード
- Instance 2 / `つむぎ`: 構築役
- Instance 3 / `さく`: 検証役

## Mattermost でよく使うコマンド

```powershell
.\scripts\mattermost.ps1 smoke --count 3
.\scripts\mattermost.ps1 lounge enable --count 3
.\scripts\mattermost.ps1 lounge status --count 3
.\scripts\mattermost.ps1 lounge run-now --count 3 --wait-seconds 15
```

まずは `smoke` で返信導線を確認し、その後に自律 chatter を試したい時だけ `lounge enable` を足すのが安全です。

## 単体起動パス

```powershell
.\scripts\init.ps1
.\scripts\doctor.ps1
.\scripts\launch.ps1 --dry-run
```

実行時の基礎コマンド:

```powershell
podman kube play --replace --no-pod-prefix .\.openclaw\pod.yaml
```
