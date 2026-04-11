---
layout: home

hero:
  name: onizuka-openclaw-autonomous-team-starter
  text: 自律型 OpenClaw チームのスターターキット
  tagline: 自律エージェントや AGI 指向開発を目指す ONIZUKA シリーズの一つとして、OpenClaw チームを立ち上げるための土台です。
  image:
    src: /header.svg
    alt: ONIZUKA シリーズの自律型 OpenClaw チームスターターのヘッダー画像
  actions:
    - theme: brand
      text: クイックスタート
      link: /ja/guide/quickstart
    - theme: alt
      text: 自律チーム導入
      link: /ja/guide/agent-teams
    - theme: alt
      text: 検証
      link: /ja/guide/validation

features:
  - title: 自律チーム用の分離実行環境
    details: "各エージェントに Podman 実行環境、config、workspace、port を分けるので、チーム全体が 1 つの状態に潰れません。"
  - title: 人格 scaffold 付き
    details: "`SOUL.md`、`IDENTITY.md`、`USER.md`、`HEARTBEAT.md`、`TOOLS.md`、`BOOTSTRAP.md` を最初から配布します。"
  - title: Mattermost 会話ラボ
    details: "ローカル Mattermost pod、bot seed、smoke test、heartbeat autonomy まで 1 つの導線で試せます。"
---

## この docs で分かること

- `uv` と PowerShell で始める Windows 前提の導入手順
- エージェントごとの workspace scaffold の役割
- Mattermost で人間と agent が会話する導線
- 検証済みモデルと validation の位置

## ONIZUKA シリーズ

このリポジトリは、自律エージェントや AGI 指向の開発を目指す ONIZUKA シリーズの一つとして位置づけています。

- [ONIZUKA AGI Co. 紹介リポジトリ](https://github.com/onizuka-agi-co/onizuka-agi-co)

## 次に読む

- [自律チーム導入](/ja/guide/agent-teams)
- [クイックスタート](/ja/guide/quickstart)
- [設定](/ja/guide/configuration)
- [検証](/ja/guide/validation)
