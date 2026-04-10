<div align="center">

# openclaw-podman-multi-pod-starter

![Project header](./assets/header.svg)

`podman kube play` ベースのファイル管理で OpenClaw を Podman 上に載せ、複数インスタンス運用や Ollama Gemma / Z.AI GLM 検証まで行うためのスターターです。

[English README](./README.md)

![CI](https://github.com/Sunwood-ai-labs/openclaw-podman-multi-pod-starter/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/github/license/Sunwood-ai-labs/openclaw-podman-multi-pod-starter)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Podman](https://img.shields.io/badge/podman-kube%20play-892CA0)

[Docs Site](https://sunwood-ai-labs.github.io/openclaw-podman-multi-pod-starter/)

</div>

## ✨ 概要

このリポジトリは、Windows から Podman 上で OpenClaw を扱うための実運用寄りスターターです。

主な特徴:

- 1 instance = 1 Podman pod = 1 OpenClaw gateway container
- state / workspace / token / port を instance ごとに分離
- `pod.yaml` を source of truth にして `podman kube play` / `podman kube down` で運用
- 3 台の独立 pod のようなローカル多重起動に対応
- `glm-5-turbo`, `gemma4:e4b`, `gemma4:e2b` の検証レポート付き

## 🧭 このリポジトリでやっていること

公式ドキュメントだけでも OpenClaw と Podman の基本は分かりますが、Windows パス処理、複数 gateway の分離、ローカルモデル検証まで含めると、手元で glue code が必要になります。

この repo はその glue をまとめています。

- `uv` 管理の小さな Python CLI
- PowerShell ラッパー
- instance ごとの config / manifest 生成
- pod 内 OpenClaw agent 実行の検証結果

## 🚀 クイックスタート

```powershell
cd D:\Prj\openclaw-podman-multi-pod-starter
uv sync
Copy-Item .env.example .env
notepad .env
.\scripts\init.ps1
.\scripts\doctor.ps1
.\scripts\launch.ps1 --dry-run
```

単一 instance では次が生成されます。

- `.openclaw/openclaw.json`
- `.openclaw/.env`
- `.openclaw/pod.yaml`

実際の起動は次に相当します。

```powershell
podman kube play --replace --no-pod-prefix .\.openclaw\pod.yaml
```

## 🧱 3台構成

```powershell
.\scripts\init.ps1 --count 3
.\scripts\launch.ps1 --count 3 --dry-run
.\scripts\status.ps1 --count 3
.\scripts\logs.ps1 --instance 2 -Follow
.\scripts\stop.ps1 --count 3 --remove
```

既定ではこう分離されます。

- Instance 1: `openclaw-1-pod` on `127.0.0.1:18789`
- Instance 2: `openclaw-2-pod` on `127.0.0.1:18791`
- Instance 3: `openclaw-3-pod` on `127.0.0.1:18793`

各 instance 配下に次が生成されます。

- `control.env`
- `.env`
- `openclaw.json`
- `pod.yaml`
- `workspace/`

scaled instance 縺ｮ繝・ぅ繝ｬ繧ｯ繝医Μ縺ｯ `agent_001` 蠖｢蠑上〒逕滓・縺輔ｌ縺ｾ縺吶・

## ????Mattermost Lounge Scripts

scaled ????? instance ??? `mattermost-tools/` ??????Mattermost lounge ????????? pod ?????????
- container path: `/home/node/.openclaw/mattermost-tools`
- runner: `mattermost_workspace_turn.py`
- helpers: `mattermost_get_state.py`, `mattermost_post_message.py`, `mattermost_create_channel.py`, `mattermost_add_reaction.py`

既定値:

- model: `ollama/gemma4:e2b`
- base URL: `http://host.containers.internal:11434`

ただし、実際に検証した Windows + WSL Podman 環境では、Windows host 上の Ollama へ届いた URL は次でした。

```text
http://172.27.208.1:11434
```

`host.containers.internal` で届かない場合は `.env` の `OPENCLAW_OLLAMA_BASE_URL` を置き換えてください。

### Z.AI

検証済みモデル:

- `zai/glm-5-turbo`

`.env` に `ZAI_API_KEY` を入れると pod へそのまま渡せます。

## ✅ 検証レポート

- [GLM-5-Turbo pod report](./reports/pod-openclaw-glm5-turbo-report.md)
- [Gemma pod report](./reports/pod-openclaw-gemma-report.md)

これらには次が含まれます。

- pod 内 health 確認
- OpenClaw agent によるファイル生成と実行
- transcript 上の `write` / `read` / `exec` 証跡

## 🛠️ 主なコマンド

```powershell
.\scripts\init.ps1
.\scripts\launch.ps1
.\scripts\status.ps1
.\scripts\logs.ps1 -Follow
.\scripts\stop.ps1 --remove
.\scripts\print-env.ps1
```

複数 instance:

```powershell
uv run openclaw-podman init --count 3
uv run openclaw-podman launch --count 3 --dry-run
uv run openclaw-podman print-env --instance 2
uv run openclaw-podman status --count 3
uv run openclaw-podman stop --count 3 --remove --dry-run
```

## 📁 構成

- `src/openclaw_podman_starter/` - helper CLI
- `scripts/` - PowerShell wrappers
- `reports/` - 検証レポート
- `.env.example` - 環境変数テンプレート

## 🔐 信頼境界

この repo は same-trust operator 向けの運用分離を想定しています。

OpenClaw の内部 sandbox ではなく、外側の Podman 境界を主な隔離手段として扱います。強い multi-tenant 分離を主張する用途には向きません。

## 🧪 CI

GitHub Actions では次を確認します。

- `uv sync`
- Python ソースの compile
- helper CLI の help 出力
- 単一 instance の init
- 複数 instance の dry-run manifest 生成

## 📚 参考

- [OpenClaw Podman docs](https://docs.openclaw.ai/install/podman)
- [OpenClaw Multiple Gateways](https://docs.openclaw.ai/gateway/multiple-gateways)
- [OpenClaw Ollama provider docs](https://docs.openclaw.ai/providers/ollama)
- [OpenClaw local models guidance](https://docs.openclaw.ai/gateway/local-models)
- [Podman kube play](https://docs.podman.io/en/latest/markdown/podman-kube-play.1.html)
- [Podman kube down](https://docs.podman.io/en/latest/markdown/podman-kube-down.1.html)
- [Ollama OpenClaw integration](https://docs.ollama.com/integrations/openclaw)

## Mattermost Lounge

regular の Mattermost lounge は、次の分担で動きます。

- 人格の source of truth は各 instance workspace の `SOUL.md` / `IDENTITY.md`
- cron job ? `mattermost-tools/mattermost_workspace_turn.py` ???
- `mattermost-tools/mattermost_*.py` ? stateless ? helper ???????? action ???????

公開チャンネルの基本:

- `triad-lab`: 3人のメイン会話 room
- `triad-open-room`: 話題が枝分かれした時の public side room
