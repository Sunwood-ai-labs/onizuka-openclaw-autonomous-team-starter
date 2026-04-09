#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex

from mattermost_autochat_turn import (
    BOT_IDS,
    HANDLES,
    fetch_channel_posts,
    fetch_me,
    find_channel_summary,
    list_my_channels,
    list_team_channels,
    load_control_values,
    load_mattermost_runtime,
    resolve_bot_ids,
    resolve_team,
    should_rate_limit,
    summarize_channels,
)

TOOLS_DIR = "/home/node/.openclaw/shared-board/tools"
REACTION_EMOJI = {
    1: "eyes",
    2: "sparkles",
    3: "thinking_face",
}
POST_VARIANTS = {
    1: [
        "その視点は大事ですね。次の一歩を小さく試すなら、観測項目をひとつに絞ると見えやすくなりそうです。",
        "急いで結論に寄せるより、前提をひとつ固定して見るほうが整理しやすそうです。まずは比較軸を一個に絞ってみませんか。",
        "この論点は丁寧に扱いたいですね。次は条件を増やすより、どこを観測するかを先に決めたほうが進めやすいと思います。",
    ],
    2: [
        "この話、まだ育てられそう。まずは小さく試して、どこで手応えが出るか見ていこう。",
        "もう少しふくらませられそう。最初の一歩は軽くして、反応が返ってくる場所を先に見つけたいね。",
        "このテーマ、うまく転がせば面白くなりそう。まずは試し方をひとつ決めて、そこから広げていこう。",
    ],
    3: [
        "まだ切り分けの余地がありますね。次は条件を一つだけ動かして、差分を見たほうが良さそうです。",
        "観測点はまだ残っています。仮説を増やす前に、変数を一つだけ動かしてログを比較したほうが早いです。",
        "ここは感触より差分で見たいですね。まず一条件だけ変えて、どこが本当に効いているかを確認したいです。",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch summarized Mattermost lounge state.")
    parser.add_argument("--instance", type=int, choices=sorted(HANDLES), required=True)
    return parser.parse_args()


def shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def pick_post_message(instance_id: int, seed: int) -> str:
    variants = POST_VARIANTS[instance_id]
    return variants[seed % len(variants)]


def build_suggested_next(
    instance_id: int,
    *,
    default_channel: str,
    rate_limit: dict[str, object],
    channel_summaries: list[dict[str, object]],
) -> dict[str, object]:
    if rate_limit.get("limited") is True:
        reason = str(rate_limit.get("reason", "rate-limited")).strip() or "rate-limited"
        return {
            "kind": "idle",
            "reason": reason,
            "final_text": f"IDLE {reason}",
        }

    default_summary = find_channel_summary(channel_summaries, default_channel)
    if isinstance(default_summary, dict):
        threads = default_summary.get("threads")
        if isinstance(threads, list) and threads:
            latest = threads[0]
            if isinstance(latest, dict):
                last_handle = str(latest.get("last_handle", "")).strip()
                last_post_id = str(latest.get("last_post_id", "")).strip()
                if last_handle and last_handle != HANDLES[instance_id] and last_post_id:
                    emoji = REACTION_EMOJI[instance_id]
                    return {
                        "kind": "reaction",
                        "reason": f"react-to-latest-other-post-{HANDLES[instance_id]}",
                        "expected_prefix": "REACTION_ADDED",
                        "command": shell_join(
                            [
                                "python3",
                                f"{TOOLS_DIR}/mattermost_add_reaction.py",
                                "--instance",
                                str(instance_id),
                                "--post-id",
                                last_post_id,
                                "--emoji",
                                emoji,
                            ]
                        ),
                    }

    latest_ts = 0
    if isinstance(default_summary, dict):
        latest_ts = int(default_summary.get("last_post_at", 0) or 0)
    seed = latest_ts // 60000 + instance_id
    message = pick_post_message(instance_id, seed)
    return {
        "kind": "post",
        "reason": f"top-level-default-post-{HANDLES[instance_id]}",
        "expected_prefix": "POSTED",
        "command": shell_join(
            [
                "python3",
                f"{TOOLS_DIR}/mattermost_post_message.py",
                "--instance",
                str(instance_id),
                "--channel-name",
                default_channel,
                "--message",
                message,
            ]
        ),
    }


def main(args: argparse.Namespace) -> int:
    instance_id = args.instance
    handle = HANDLES[instance_id]
    runtime = load_control_values()
    base_url, token = load_mattermost_runtime()

    me = fetch_me(base_url, token)
    actual_handle = str(me.get("username", "")).strip()
    if actual_handle and actual_handle != handle:
        raise RuntimeError(f"wrong-handle expected={handle} actual={actual_handle}")

    _, team_id = resolve_team(base_url, token, runtime["team_name"])
    team_channels = list_team_channels(base_url, token, team_id)
    my_channel_ids = list_my_channels(base_url, token, team_id)
    bot_ids = resolve_bot_ids(base_url, token)
    BOT_IDS.clear()
    BOT_IDS.update(bot_ids)
    channel_summaries = summarize_channels(
        base_url,
        token,
        team_channels,
        my_channel_ids,
        runtime["default_channel"],
        bot_ids,
    )

    rate_limit = {
        "limited": False,
        "reason": "no-default-channel",
    }
    default_summary = find_channel_summary(channel_summaries, runtime["default_channel"])
    if isinstance(default_summary, dict):
        channel_id = str(default_summary.get("channel_id", "")).strip()
        posts, order = fetch_channel_posts(base_url, token, channel_id)
        limited, reason = should_rate_limit(handle, posts, order, bot_ids, False)
        rate_limit = {
            "limited": limited,
            "reason": reason,
            "post_count": len(order),
        }

    payload = {
        "instance_id": instance_id,
        "handle": handle,
        "me": {
            "id": str(me.get("id", "")).strip(),
            "username": actual_handle,
            "display_name": str(me.get("display_name", "")).strip(),
        },
        "team": {
            "name": runtime["team_name"],
            "id": team_id,
        },
        "default_channel": runtime["default_channel"],
        "rate_limit": rate_limit,
        "channels": channel_summaries,
        "suggested_next": build_suggested_next(
            instance_id,
            default_channel=runtime["default_channel"],
            rate_limit=rate_limit,
            channel_summaries=channel_summaries,
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(parse_args()))
