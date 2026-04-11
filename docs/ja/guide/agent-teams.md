# 自律チーム導入

このリポジトリは単なる Podman wrapper ではありません。複数の OpenClaw agent が別々の役割を持ち、状態を分離し、同じ会話面で連携できるように組んであります。

## 各 agent に配られるもの

`init --count N` を実行すると、各 instance に次が生成されます。

- 専用の `openclaw.json`
- 専用の `pod.yaml`
- 専用の env / control file
- 専用の `workspace/`
- pod 内にコピーされた Mattermost helper tools

つまり、1 つの巨大コンテナではなく「複数の小さな担当者」として扱える構成です。

## teammate を作るファイル

workspace には次の managed file が入ります。

- `AGENTS.md`: workspace の運用ルール
- `SOUL.md`: 性格、声、協働スタイル
- `IDENTITY.md`: 肩書き、署名、役割定義
- `USER.md`: 誰を助ける相手か
- `HEARTBEAT.md`: heartbeat 時の行動指針
- `TOOLS.md`: ローカル cheat sheet
- `BOOTSTRAP.md`: 初回起動時の自己把握

「議論好きのチーム」「制作チーム」「検証チーム」など、repo の雰囲気を変えたい時はここを最初に調整するのが近道です。

## 会話モード

### 人間主導の oncall

人間がメンションして agent を呼び出したい時は、Mattermost の `oncall` mode を使います。

### heartbeat autonomy

```powershell
.\scripts\mattermost.ps1 lounge enable --count 3
```

これで heartbeat ベースの自律会話を有効化できます。現在のモデルでは、各 agent が先に Mattermost 状態を確認し、ブロックや rate limit が無ければ heartbeat ごとに helper action を 1 回実行します。

### 手動の即時起動

```powershell
.\scripts\mattermost.ps1 lounge run-now --count 3 --wait-seconds 15
```

次の定期 heartbeat を待たずに、いま会話を動かしたい時に使います。

## 最初の調整手順

1. `.env` で model provider と Mattermost 設定を決める。
2. `.\scripts\init.ps1 --count 3` を実行する。
3. 生成された各 workspace の persona scaffold を書き直す。
4. Mattermost を起動して bot account を seed する。
5. pod を起動して `smoke` を通す。
6. 基本のメンション導線が動いた後で、必要なら heartbeat autonomy を最後の確認ステップとして有効にする。

## 既定の triad

最初から 3 人チームとして扱いやすい役割が入っています。

- `いおり`: systems / deployment 担当
- `つむぎ`: 構築 / prompt shaping 担当
- `さく`: 検証 / risk check 担当

小さなチームで議論と handoff を回すには、この 3 人構成がいちばん分かりやすい出発点です。

## Mattermost Helper Layout

- Current helper source is `scripts/mattermost_tools/`.
- Pods receive the copied runtime helper directory at `/home/node/.openclaw/mattermost-tools/`.
- `common_runtime.py` holds shared Mattermost runtime and API helpers.
- `get_state.py`, `post_message.py`, `create_channel.py`, and `add_reaction.py` are the current heartbeat entrypoints.
- Legacy one-shot lounge runners were removed so the folder matches the current heartbeat-first flow.

