# 検証

## 同梱レポート

- [GLM-5-Turbo report](https://github.com/Sunwood-ai-labs/onizuka-openclaw-autonomous-team-starter/blob/main/reports/pod-openclaw-glm5-turbo-report.md)
- [Gemma report](https://github.com/Sunwood-ai-labs/onizuka-openclaw-autonomous-team-starter/blob/main/reports/pod-openclaw-gemma-report.md)

## 確認していること

- pod 内 health check
- pod 内 OpenClaw agent の応答
- tool call 経由の file generation / execution
- session transcript 上の `write` / `read` / `exec` 証跡

一部の report には、検証当時のローカル path、room 名、runtime identifier がそのまま残ります。

## 会話ラボの運用スモークテスト

Mattermost 側の配線を確認したい時は次を使います。

```powershell
.\scripts\mattermost.ps1 smoke --count 3
```

これは seed 済み bot の返信確認を行う運用 smoke であり、将来のすべての自律会話を一括で証明するものではありません。

関連する lab 証跡:

- [Mattermost autonomy QA inventory](https://github.com/Sunwood-ai-labs/onizuka-openclaw-autonomous-team-starter/blob/main/reports/qa-inventory-mattermost-autochat-2026-04-09.md)

既定の seed room は `triad-lab` ですが、workspace 指示や lab 構成によっては追加の public room を使う場合もあります。

## 検証済みモデル

- `zai/glm-5-turbo`
- `ollama/gemma4:e4b`
- `ollama/gemma4:e2b`
