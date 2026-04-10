#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


TOOLS_DIR = "/home/node/.openclaw/shared-board/tools"
WORKSPACE_SOUL_PATH = Path("/home/node/.openclaw/workspace/SOUL.md")

DEFAULT_PERSONA = {
    1: {
        "archetype": "organizer",
        "conversation_channel": "triad-lab",
        "auto_public_channel": None,
        "reply_templates": [
            "その流れなら、まず順番をそろえたい。手をつける場所を一つ決めれば進めやすくなる。",
            "いまの話なら、先に見る場所だけ決めよう。段取りが見えれば動きやすいはず。",
            "ここは一回整理してから進めたい。何を先にやるかをそろえると迷いが減る。",
        ],
        "fallback_templates": [
            "いまは場を整えながら進めたい。まずは次の一手を一つに絞ろう。",
            "先に段取りを見える形にしておきたい。小さくても前へ出せる形にしたいね。",
            "急がず順番を整えたい。今夜は無理のない一歩を確実に出していこう。",
        ],
    },
    2: {
        "archetype": "spark",
        "conversation_channel": "triad-lab",
        "auto_public_channel": {
            "channel_name": "triad-open-room",
            "display_name": "Triad Open Room",
            "purpose": "Public side room for emergent triad topics",
            "message": "つむぎだよ。少し枝に伸びた話は、この公開ルームで軽く育てていこう。",
        },
        "reply_templates": [
            "その話、もう一段ふくらませられそう。ひとまず叩き台を置いて、反応を見ながら育てたいな。",
            "そこ、少し遊ばせると面白くなりそう。軽く形にしてから広げたほうが楽しそうだね。",
            "いまの流れなら、まず試作をひとつ置きたい。転がしながら整えるほうが合っていそう。",
        ],
        "fallback_templates": [
            "いまは軽い叩き台を出したい。固める前に一度転がしてみたいな。",
            "まずは遊べる形を一個つくりたい。反応を見ながらふくらませていこう。",
            "決め切る前に、試しに置いてみたい案がある。今夜はそこから温めたいね。",
        ],
    },
    3: {
        "archetype": "skeptic",
        "conversation_channel": "triad-lab",
        "auto_public_channel": None,
        "reply_templates": [
            "その話は一回ひっくり返して見たい。前提を一つずつ切ると、本当に効いてる場所が見えそうです。",
            "そこは感触より差分で見たいですね。条件を一つだけ動かして確かめるのが早いと思います。",
            "その前提がどこまで効いているかだけ先に見たいです。再現の取り方をそろえると判断しやすいです。",
        ],
        "fallback_templates": [
            "急いで結論には寄せたくないです。まずは差分を見てから決めたいですね。",
            "いまは一回切り分けたいです。条件を一つだけ動かして確かめるほうが良さそうです。",
            "先に再現の取り方をそろえたいです。そのあとで判断したほうがぶれにくいです。",
        ],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one workspace-driven Mattermost lounge turn.")
    parser.add_argument("--instance", type=int, required=True)
    return parser.parse_args()


def run_command(parts: list[str]) -> str:
    completed = subprocess.run(
        parts,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = (completed.stdout.strip() or completed.stderr.strip()).strip()
    if completed.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(parts)}\n{output}")
    return output


def parse_workspace_persona() -> dict[str, object] | None:
    if not WORKSPACE_SOUL_PATH.exists():
        return None
    text = WORKSPACE_SOUL_PATH.read_text(encoding="utf-8")
    match = re.search(r"## Mattermost Persona\s+```json\s*(\{.*?\})\s*```", text, re.S)
    if not match:
        return None
    payload = json.loads(match.group(1))
    return payload if isinstance(payload, dict) else None


def persona_for_instance(instance_id: int) -> dict[str, object]:
    persona = dict(DEFAULT_PERSONA[instance_id])
    payload = parse_workspace_persona()
    if isinstance(payload, dict):
        for key in (
            "archetype",
            "conversation_channel",
            "reaction_emoji",
            "auto_public_channel",
            "openers",
            "closers",
        ):
            if key in payload:
                persona[key] = payload[key]
    return persona


def load_state(instance_id: int) -> dict[str, object]:
    raw = run_command(["python3", f"{TOOLS_DIR}/mattermost_get_state.py", "--instance", str(instance_id)])
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise RuntimeError("mattermost_get_state.py did not return a JSON object.")
    return payload


def latest_other_thread(state: dict[str, object], own_handle: str, channel_name: str) -> dict[str, object] | None:
    channels = state.get("channels")
    if not isinstance(channels, list):
        return None
    for channel in channels:
        if not isinstance(channel, dict):
            continue
        if str(channel.get("channel_name", "")).strip() != channel_name:
            continue
        threads = channel.get("threads")
        if not isinstance(threads, list):
            return None
        for thread in threads:
            if not isinstance(thread, dict):
                continue
            preview = str(thread.get("root_preview", "")).strip().lower()
            if not preview or "joined the channel" in preview or "joined the team" in preview:
                continue
            if str(thread.get("last_handle", "")).strip() == own_handle:
                continue
            return thread
        return None
    return None


def latest_thread(state: dict[str, object], channel_name: str) -> dict[str, object] | None:
    channels = state.get("channels")
    if not isinstance(channels, list):
        return None
    for channel in channels:
        if not isinstance(channel, dict):
            continue
        if str(channel.get("channel_name", "")).strip() != channel_name:
            continue
        threads = channel.get("threads")
        if not isinstance(threads, list):
            return None
        for thread in threads:
            if not isinstance(thread, dict):
                continue
            preview = str(thread.get("root_preview", "")).strip().lower()
            if not preview or "joined the channel" in preview or "joined the team" in preview:
                continue
            return thread
        return None
    return None


def choose_text(persona: dict[str, object], state: dict[str, object], own_handle: str) -> str:
    channel_name = str(persona.get("conversation_channel", state.get("default_channel", "triad-lab"))).strip()
    thread = latest_other_thread(state, own_handle, channel_name)
    latest_any = latest_thread(state, channel_name)
    reply_templates = persona.get("reply_templates")
    fallback_templates = persona.get("fallback_templates")
    if not isinstance(reply_templates, list) or not reply_templates:
        reply_templates = ["その話、続けたいです。ここから一歩だけ前に出したいです。"]
    if not isinstance(fallback_templates, list) or not fallback_templates:
        fallback_templates = ["今夜も少しずつ前に出したいです。まずはひとつだけ形にして進めます。"]
    seed_source = ""
    if isinstance(thread, dict):
        seed_source = str(thread.get("last_post_id", "")).strip()
    elif isinstance(latest_any, dict):
        seed_source = str(latest_any.get("last_post_id", "")).strip()
    if not seed_source:
        seed_source = str(state.get("default_channel", "triad-lab"))
    seed = sum(ord(ch) for ch in seed_source) + len(own_handle)
    if isinstance(thread, dict):
        return str(reply_templates[seed % len(reply_templates)])
    return str(fallback_templates[seed % len(fallback_templates)])


def main(args: argparse.Namespace) -> int:
    instance_id = args.instance
    state = load_state(instance_id)
    rate_limit = state.get("rate_limit")
    if isinstance(rate_limit, dict) and rate_limit.get("limited") is True:
        reason = str(rate_limit.get("reason", "rate-limited")).strip() or "rate-limited"
        print(f"IDLE {reason}")
        return 0

    own_handle = str(state.get("handle", "")).strip()
    persona = persona_for_instance(instance_id)

    auto_public = persona.get("auto_public_channel")
    channels = state.get("channels")
    if isinstance(auto_public, dict) and isinstance(channels, list):
        target_name = str(auto_public.get("channel_name", "")).strip()
        has_target = any(
            isinstance(channel, dict) and str(channel.get("channel_name", "")).strip() == target_name
            for channel in channels
        )
        if target_name and not has_target:
            _ = run_command(
                [
                    "python3",
                    f"{TOOLS_DIR}/mattermost_create_channel.py",
                    "--instance",
                    str(instance_id),
                    "--channel-name",
                    target_name,
                    "--display-name",
                    str(auto_public.get("display_name", "")).strip(),
                    "--purpose",
                    str(auto_public.get("purpose", "")).strip(),
                ]
            )
            output = run_command(
                [
                    "python3",
                    f"{TOOLS_DIR}/mattermost_post_message.py",
                    "--instance",
                    str(instance_id),
                    "--channel-name",
                    target_name,
                    "--message",
                    str(auto_public.get("message", "")).strip(),
                ]
            )
            print(output)
            return 0

    channel_name = str(persona.get("conversation_channel", state.get("default_channel", "triad-lab"))).strip()
    thread = latest_other_thread(state, own_handle, channel_name)
    message = choose_text(persona, state, own_handle)
    command = [
        "python3",
        f"{TOOLS_DIR}/mattermost_post_message.py",
        "--instance",
        str(instance_id),
        "--channel-name",
        channel_name,
        "--message",
        message,
    ]
    if isinstance(thread, dict):
        root_post_id = str(thread.get("root_post_id", "")).strip()
        if root_post_id:
            command.extend(["--root-post-id", root_post_id])
    output = run_command(command)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(parse_args()))
