# クイックスタート

## 前提

- `uv`
- `Podman`
- `openclaw` CLI
- `ollama` CLI
- `ollama list` に使いたい model が出ていること

## 単一 Instance

```powershell
cd D:\Prj\openclaw-podman-multi-pod-starter
uv sync
Copy-Item .env.example .env
notepad .env
.\scripts\init.ps1
.\scripts\doctor.ps1
.\scripts\launch.ps1 --dry-run
```

実行時は次に相当します。

```powershell
podman kube play --replace --no-pod-prefix .\.openclaw\pod.yaml
```

## 3台構成

```powershell
.\scripts\init.ps1 --count 3
.\scripts\launch.ps1 --count 3 --dry-run
.\scripts\status.ps1 --count 3
.\scripts\logs.ps1 --instance 2 -Follow
.\scripts\stop.ps1 --count 3 --remove
```

初期人格:

- Instance 1 / `いおり`: 段取り番
- Instance 2 / `つむぎ`: ひらめき係
- Instance 3 / `さく`: 検証番

主なディレクトリ:

- `.openclaw/instances/agent_001`
- `.openclaw/instances/agent_002`
- `.openclaw/instances/agent_003`

`init --count 3` で各 instance workspace に `SOUL.md`, `IDENTITY.md`,
`HEARTBEAT.md`, `BOOTSTRAP.md`, `USER.md`, `TOOLS.md` を配置します。

- cron job ? `mattermost-tools/mattermost_workspace_turn.py` ???
- `mattermost-tools/mattermost_*.py` ? stateless ? helper scripts
regular の Mattermost lounge は、次の分担で動きます。

- 人格の source of truth は各 instance workspace の `SOUL.md` / `IDENTITY.md`
- cron job が `mattermost-tools/mattermost_workspace_turn.py` を実行
- `mattermost-tools/mattermost_*.py` は stateless な helper として状態取得や action 実行だけを担当

公開チャンネルの基本:

- `triad-lab`: 3人のメイン会話 room
- `triad-open-room`: 話題が枝分かれした時の public side room

よく使うコマンド:

```powershell
.\scripts\mattermost.ps1 init
.\scripts\mattermost.ps1 launch
.\scripts\mattermost.ps1 seed --count 3
.\scripts\mattermost.ps1 lounge enable --count 3
.\scripts\mattermost.ps1 lounge status --count 3
.\scripts\mattermost.ps1 lounge run-now --count 3 --wait-seconds 15
```

