#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path

from mattermost_autochat_turn import (
    BOT_IDS,
    HANDLES,
    fetch_channel_posts,
    fetch_me,
    find_channel_summary,
    is_meaningful_thread,
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
WORKSPACE_SOUL_PATH = Path("/home/node/.openclaw/workspace/SOUL.md")

DEFAULT_PERSONA_CONFIG: dict[int, dict[str, object]] = {
    1: {
        "reaction_emoji": "eyes",
        "channel_preference": ["triad-lab", "triad-open-room", "triad-free-talk"],
        "post_variants": [
            "その視点は大事ですね。次の一歩を小さく試すなら、観測項目をひとつに絞ると見えやすくなりそうです。",
            "急いで結論に寄せるより、前提をひとつ固定して見るほうが整理しやすそうです。まずは比較軸を一個に絞ってみませんか。",
            "この論点は丁寧に扱いたいですね。次は条件を増やすより、どこを観測するかを先に決めたほうが進めやすいと思います。",
        ],
        "auto_public_channel": None,
    },
    2: {
        "reaction_emoji": "sparkles",
        "channel_preference": ["triad-open-room", "triad-lab", "triad-free-talk"],
        "post_variants": [
            "この話、まだ育てられそう。まずは小さく試して、どこで手応えが出るか見ていこう。",
            "もう少しふくらませられそう。最初の一歩は軽くして、反応が返ってくる場所を先に見つけたいね。",
            "このテーマ、うまく転がせば面白くなりそう。まずは試し方をひとつ決めて、そこから広げていこう。",
        ],
        "auto_public_channel": {
            "channel_name": "triad-open-room",
            "display_name": "Triad Open Room",
            "purpose": "Public side room for emergent triad topics",
            "message": "新しい公開チャンネルをひとつ用意しました。少し枝分かれした話題や試し書きは、ここで軽く育てていきましょう。",
        },
    },
    3: {
        "reaction_emoji": "thinking_face",
        "channel_preference": ["triad-free-talk", "triad-open-room", "triad-lab"],
        "post_variants": [
            "まだ切り分けの余地がありますね。次は条件を一つだけ動かして、差分を見たほうが良さそうです。",
            "観測点はまだ残っています。仮説を増やす前に、変数を一つだけ動かしてログを比較したほうが早いです。",
            "ここは感触より差分で見たいですね。まず一条件だけ変えて、どこが本当に効いているかを確認したいです。",
        ],
        "auto_public_channel": None,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch summarized Mattermost lounge state.")
    parser.add_argument("--instance", type=int, choices=sorted(HANDLES), required=True)
    return parser.parse_args()


def shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def default_persona_config(instance_id: int) -> dict[str, object]:
    return dict(DEFAULT_PERSONA_CONFIG[instance_id])


def parse_workspace_persona_block(text: str) -> dict[str, object] | None:
    match = re.search(r"## Mattermost Persona\s+```json\s*(\{.*?\})\s*```", text, re.S)
    if not match:
        return None
    payload = json.loads(match.group(1))
    return payload if isinstance(payload, dict) else None


def load_workspace_persona(instance_id: int) -> dict[str, object]:
    persona = default_persona_config(instance_id)
    if not WORKSPACE_SOUL_PATH.exists():
        return persona
    try:
        payload = parse_workspace_persona_block(WORKSPACE_SOUL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return persona
    if not isinstance(payload, dict):
        return persona
    for key in ("reaction_emoji", "channel_preference", "post_variants", "auto_public_channel"):
        if key in payload:
            persona[key] = payload[key]
    return persona


def pick_post_message(persona: dict[str, object], seed: int) -> str:
    variants = persona.get("post_variants")
    if not isinstance(variants, list) or not variants:
        variants = default_persona_config(int(persona.get("instance_id", 1))).get("post_variants", [])
    return str(variants[seed % len(variants)])


def flatten_reaction_candidates(
    instance_id: int,
    channel_summaries: list[dict[str, object]],
) -> list[tuple[dict[str, object], dict[str, object]]]:
    handle = HANDLES[instance_id]
    candidates: list[tuple[dict[str, object], dict[str, object]]] = []
    for channel in channel_summaries:
        threads = channel.get("threads")
        if not isinstance(threads, list):
            continue
        for thread in threads:
            if not isinstance(thread, dict):
                continue
            if not is_meaningful_thread(thread):
                continue
            last_handle = str(thread.get("last_handle", "")).strip()
            last_post_id = str(thread.get("last_post_id", "")).strip()
            if not last_post_id or not last_handle or last_handle == handle:
                continue
            candidates.append((channel, thread))
    candidates.sort(key=lambda item: int(item[1].get("last_ts", 0) or 0), reverse=True)
    return candidates


def preferred_post_channel(
    persona: dict[str, object],
    default_channel: str,
    channel_summaries: list[dict[str, object]],
) -> dict[str, object] | None:
    by_name = {
        str(channel.get("channel_name", "")).strip(): channel
        for channel in channel_summaries
        if isinstance(channel, dict)
    }
    preference = persona.get("channel_preference")
    channel_names = preference if isinstance(preference, list) and preference else [default_channel]
    for channel_name in channel_names:
        channel = by_name.get(str(channel_name))
        if channel is None:
            continue
        threads = channel.get("threads")
        if isinstance(threads, list) and threads:
            latest = threads[0]
            if isinstance(latest, dict) and str(latest.get("last_handle", "")).strip() == str(persona.get("handle", "")):
                continue
        return channel
    return by_name.get(default_channel) or next(iter(by_name.values()), None)


def build_post_seed(instance_id: int, channel: dict[str, object] | None) -> int:
    if not isinstance(channel, dict):
        return instance_id
    threads = channel.get("threads")
    latest = threads[0] if isinstance(threads, list) and threads else {}
    source = str(getattr(latest, "get", lambda *_: "")("last_post_id", "")).strip()
    if not source:
        source = f"{channel.get('channel_name', '')}:{channel.get('last_post_at', 0) or 0}"
    return sum(ord(ch) for ch in source) + instance_id


def build_suggested_next(
    instance_id: int,
    *,
    default_channel: str,
    rate_limit: dict[str, object],
    channel_summaries: list[dict[str, object]],
) -> dict[str, object]:
    persona = load_workspace_persona(instance_id)
    persona["instance_id"] = instance_id
    persona["handle"] = HANDLES[instance_id]

    if rate_limit.get("limited") is True:
        reason = str(rate_limit.get("reason", "rate-limited")).strip() or "rate-limited"
        return {
            "kind": "idle",
            "reason": reason,
            "final_text": f"IDLE {reason}",
        }

    triad_channels = [
        channel
        for channel in channel_summaries
        if str(channel.get("channel_name", "")).startswith("triad-")
    ]
    auto_public = persona.get("auto_public_channel")
    has_auto_public_channel = isinstance(auto_public, dict) and any(
        str(channel.get("channel_name", "")).strip() == str(auto_public.get("channel_name", "")).strip()
        for channel in channel_summaries
    )
    if isinstance(auto_public, dict) and not has_auto_public_channel and len(triad_channels) < 4:
        channel_name = str(auto_public.get("channel_name", "")).strip()
        return {
            "kind": "create_channel",
            "reason": f"create-shared-public-room-{HANDLES[instance_id]}",
            "expected_prefix": "POSTED",
            "command": shell_join(
                [
                    "python3",
                    f"{TOOLS_DIR}/mattermost_create_channel.py",
                    "--instance",
                    str(instance_id),
                    "--channel-name",
                    channel_name,
                    "--display-name",
                    str(auto_public.get("display_name", "")).strip(),
                    "--purpose",
                    str(auto_public.get("purpose", "")).strip(),
                ]
            ),
            "followup_command": shell_join(
                [
                    "python3",
                    f"{TOOLS_DIR}/mattermost_post_message.py",
                    "--instance",
                    str(instance_id),
                    "--channel-name",
                    channel_name,
                    "--message",
                    str(auto_public.get("message", "")).strip(),
                ]
            ),
        }

    reaction_candidates = flatten_reaction_candidates(instance_id, channel_summaries)
    if reaction_candidates:
        _, latest = reaction_candidates[0]
        emoji = str(persona.get("reaction_emoji", "eyes")).strip() or "eyes"
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
                    str(latest.get("last_post_id", "")).strip(),
                    "--emoji",
                    emoji,
                ]
            ),
        }

    target_channel = preferred_post_channel(persona, default_channel, channel_summaries)
    target_channel_name = default_channel
    if isinstance(target_channel, dict):
        target_channel_name = str(target_channel.get("channel_name", "")).strip() or default_channel
    seed = build_post_seed(instance_id, target_channel)
    message = pick_post_message(persona, seed)
    return {
        "kind": "post",
        "reason": f"top-level-post-{HANDLES[instance_id]}",
        "expected_prefix": "POSTED",
        "command": shell_join(
            [
                "python3",
                f"{TOOLS_DIR}/mattermost_post_message.py",
                "--instance",
                str(instance_id),
                "--channel-name",
                target_channel_name,
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
