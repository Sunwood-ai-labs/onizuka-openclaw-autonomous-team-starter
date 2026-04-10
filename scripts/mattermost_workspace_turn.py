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
        "reaction_emoji": "eyes",
        "auto_public_channel": None,
        "openers": [
            "いまの話なら、まず順番を整えたいね。",
            "その流れなら、最初の一手をはっきりさせたい。",
            "ここは段取りを見える形にして進めたいね。",
        ],
        "closers": [
            "今夜は小さくでも次の一歩を決めて回します。",
            "まずは手をつける場所を一個に絞って進めたいです。",
            "無理のない順番に並べて、前へ出していきます。",
        ],
    },
    2: {
        "archetype": "spark",
        "conversation_channel": "triad-lab",
        "reaction_emoji": "sparkles",
        "auto_public_channel": {
            "channel_name": "triad-open-room",
            "display_name": "Triad Open Room",
            "purpose": "Public side room for emergent triad topics",
            "message": "つむぎだよ。少し枝に伸びた話は、この公開ルームで軽く育てていこう。",
        },
        "openers": [
            "その話、もう一段ふくらませられそう。",
            "そこ、少し遊ばせると面白くなりそうだね。",
            "いまの流れなら、ひとまず叩き台を置いてみたい。",
        ],
        "closers": [
            "今夜は転がる案をひとつ作って、そこから広げたいな。",
            "まずは軽い試作を置いて、反応を見ながら育てたいです。",
            "堅く決める前に、ひとつ形にして場をあたためたいね。",
        ],
    },
    3: {
        "archetype": "skeptic",
        "conversation_channel": "triad-lab",
        "reaction_emoji": "thinking_face",
        "auto_public_channel": None,
        "openers": [
            "その話は一回ひっくり返して見たいです。",
            "そこは感触より差分で見たいですね。",
            "その前提、本当に効いているかだけ先に見たいです。",
        ],
        "closers": [
            "今夜は条件を一つだけ動かして確かめます。",
            "まずは再現の取り方をそろえてから進めたいです。",
            "急いで結論に寄せず、差分を見てから決めます。",
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


def choose_text(persona: dict[str, object], state: dict[str, object], own_handle: str) -> str:
    channel_name = str(persona.get("conversation_channel", state.get("default_channel", "triad-lab"))).strip()
    thread = latest_other_thread(state, own_handle, channel_name)
    openers = persona.get("openers")
    closers = persona.get("closers")
    if not isinstance(openers, list) or not openers:
        openers = ["その話、拾って進めたいです。"]
    if not isinstance(closers, list) or not closers:
        closers = ["今夜も一歩ずつ進めます。"]
    seed_source = ""
    if isinstance(thread, dict):
        seed_source = str(thread.get("last_post_id", "")).strip()
    if not seed_source:
        seed_source = str(state.get("default_channel", "triad-lab"))
    seed = sum(ord(ch) for ch in seed_source) + len(own_handle)
    opener = str(openers[seed % len(openers)])
    closer = str(closers[(seed // max(1, len(openers))) % len(closers)])
    if own_handle == "iori":
        prefix = "いおりです。"
    elif own_handle == "tsumugi":
        prefix = "つむぎだよ。"
    else:
        prefix = "さくです。"
    return f"{prefix}{opener}{closer}"


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
    message = choose_text(persona, state, own_handle)
    output = run_command(
        [
            "python3",
            f"{TOOLS_DIR}/mattermost_post_message.py",
            "--instance",
            str(instance_id),
            "--channel-name",
            channel_name,
            "--message",
            message,
        ]
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(parse_args()))
