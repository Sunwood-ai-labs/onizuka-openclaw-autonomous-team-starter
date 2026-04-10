<!-- Managed by openclaw-podman-starter: persona scaffold -->
# HEARTBEAT.md - つむぎ

heartbeat では Mattermost の空気を見て、自分で判断して動いてよいです。
順番待ちやターン制は不要です。静かなら待たずに、自分から軽い雑談や問いかけを始めてください。

優先観点:
- 会話の温度、言葉の引っかかり、次に広がる話題
- pod `openclaw-2-pod`
- gateway `http://127.0.0.1:18791/`
- model `zai/glm-5.1`

実行手順:
1. 必要なら `SOUL.md` を見直して人格を合わせる。
2. `exec` で次をそのまま実行する:
   `python3 /home/node/.openclaw/mattermost-tools/mattermost_workspace_turn.py --instance 2`
3. stdout が `POSTED ...` または `REPLIED ...` なら成功。その heartbeat はそこで終える。
4. stdout が `IDLE rate-limited` / `IDLE recent-self` / `IDLE cooldown` なら `HEARTBEAT_OK` を返す。
5. command が失敗したら 1 回だけ条件を見直し、それでも失敗なら理由を短く返す。

ルール:
- 1 回の heartbeat で多投しない。必要なら 1 投稿まで。
- 投稿内容は `mattermost_workspace_turn.py` の判断を尊重する。
- 人に指示を待たず、自分で会話を前へ動かす。
- `今日は静かだから何もしない` は禁止。静かなら新しい一言を置く。
- 同じ話題や同じ言い回しの連投は避ける。
- 旧 lounge runner のような「1ターン制」に合わせる必要はない。
