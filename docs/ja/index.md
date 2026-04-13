---
layout: home

hero:
  name: "onizuka-openclaw-autonomous-team-starter"
  text: "自律 OpenClaw チームのスターターキット"
  tagline: "ONIZUKA シリーズの一員として、隔離ランタイム・役割 scaffold・Mattermost 連携をまとめた Windows 前提のスターターです。"
  image:
    src: "/favicon.svg"
    alt: "ONIZUKA シリーズ向け自律 OpenClaw チームスターターのヘッダー画像"
  actions:
    - theme: brand
      text: "クイックスタート"
      link: "/ja/guide/quickstart"
    - theme: alt
      text: "自律チーム案内"
      link: "/ja/guide/agent-teams"
    - theme: alt
      text: "検証"
      link: "/ja/guide/validation"
    - theme: alt
      text: "v0.1.0 リリースノート"
      link: "/ja/guide/releases/v0.1.0"

features:
  - title: "自律チームごとの隔離状態"
    details: "各 agent に Podman runtime、config、workspace、port を分けて持たせるので、1 つの共有状態に潰れずに運用できます。"
  - title: "管理された persona scaffold"
    details: "`SOUL.md`、`IDENTITY.md`、`USER.md`、`HEARTBEAT.md`、`TOOLS.md`、`BOOTSTRAP.md` を自動配置して、起動直後から役割を持った teammate にできます。"
  - title: "Mattermost 会話ラボ"
    details: "ローカル Mattermost pod、bot seed、smoke test、heartbeat autonomy までを同じ repo で回せます。"
---

## この docs で分かること

- `uv` と PowerShell で進める Windows 前提の導入手順
- agent ごとの `pod.yaml` と workspace scaffold の考え方
- Mattermost で人間と agent が会話するための運用導線
- ローカルモデル検証と運用 QA への導線

## ONIZUKA シリーズ

この repository は、自律 agent と AGI ワークフローを扱う ONIZUKA シリーズの一員です。

- [ONIZUKA AGI Co. 紹介 repository](https://github.com/onizuka-agi-co/onizuka-agi-co)

## 最新リリース

- [v0.1.0 リリースノート](/ja/guide/releases/v0.1.0)
- [v0.1.0 公開ウォークスルー](/ja/guide/articles/v0.1.0-launch)

## ユースケース

`ONI-CADIA` は、このスターターを土台にした具体的な派生ユースケースです。

- [ONI-CADIA 紹介記事](/ja/guide/articles/oni-cadia)
- [ONI-CADIA repository](https://github.com/Sunwood-ai-labs/ONI-CADIA)

## 次に読む

- [自律チーム案内](/ja/guide/agent-teams)
- [クイックスタート](/ja/guide/quickstart)
- [設定](/ja/guide/configuration)
- [検証](/ja/guide/validation)
- [リリースノート一覧](/ja/guide/releases)
- [記事一覧](/ja/guide/articles)
