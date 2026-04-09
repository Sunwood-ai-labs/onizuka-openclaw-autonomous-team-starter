#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
from pathlib import Path


TOOLS_DIR = "/home/node/.openclaw/shared-board/tools"
WORKSPACE_SOUL_PATH = Path("/home/node/.openclaw/workspace/SOUL.md")

DEFAULT_PERSONA = {
    1: {
        "archetype": "organizer",
        "reaction_emoji": "eyes",
        "channel_preference": ["triad-lab", "triad-open-room", "triad-free-talk"],
        "post_variants": [
            "いおりです。場を整えつつ、次に何をやるかを見える形にして進めます。",
            "いおりです。ふわっとした話でも、今夜の動きに落として回していきます。",
            "いおりです。まず状況をそろえて、無理のない段取りから前へ出します。",
        ],
    },
    2: {
        "archetype": "spark",
        "reaction_emoji": "sparkles",
        "channel_preference": ["triad-open-room", "triad-lab", "triad-free-talk"],
        "post_variants": [
            "つむぎだよ。まずは叩き台を軽く出して、面白く育つ流れを作りたいな。",
            "つむぎです。今夜は思いつきをひとつ形にして、そこから広げていきたいです。",
            "つむぎだよ。堅く決めすぎず、まずは転がる案を作って場をあたためたいな。",
        ],
        "auto_public_channel": {
            "channel_name": "triad-open-room",
            "display_name": "Triad Open Room",
            "purpose": "Public side room for emergent triad topics",
            "message": "つむぎだよ。少し枝に伸びた話は、この公開ルームで軽く育てていこう。",
        },
    },
    3: {
        "archetype": "skeptic",
        "reaction_emoji": "thinking_face",
        "channel_preference": ["triad-free-talk", "triad-open-room", "triad-lab"],
        "post_variants": [
            "さくです。まずは差分を見るところから始めます。感触より検証を先に置きたいです。",
            "さくです。今夜は一回ひっくり返して、どこが本当に効いているかを見ます。",
            "さくです。急いで結論に寄せず、まず条件を切って確認したいです。",
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
        for key in ("archetype", "reaction_emoji", "channel_preference", "post_variants", "auto_public_channel"):
            if key in payload:
                persona[key] = payload[key]
    return persona


def load_state(instance_id: int) -> dict[str, object]:
    raw = run_command(["python3", f"{TOOLS_DIR}/mattermost_get_state.py", "--instance", str(instance_id)])
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise RuntimeError("mattermost_get_state.py did not return a JSON object.")
    return payload


def meaningful_threads(state: dict[str, object], own_handle: str) -> list[tuple[dict[str, object], dict[str, object]]]:
    channels = state.get("channels")
    if not isinstance(channels, list):
        return []
    result: list[tuple[dict[str, object], dict[str, object]]] = []
    for channel in channels:
        if not isinstance(channel, dict):
            continue
        threads = channel.get("threads")
        if not isinstance(threads, list):
            continue
        for thread in threads:
            if not isinstance(thread, dict):
                continue
            preview = str(thread.get("root_preview", "")).strip().lower()
            if not preview or "joined the channel" in preview or "joined the team" in preview:
                continue
            last_handle = str(thread.get("last_handle", "")).strip()
            last_post_id = str(thread.get("last_post_id", "")).strip()
            if not last_post_id or not last_handle or last_handle == own_handle:
                continue
            result.append((channel, thread))
    result.sort(key=lambda item: int(item[1].get("last_ts", 0) or 0), reverse=True)
    return result


def preferred_post_channel(state: dict[str, object], persona: dict[str, object], own_handle: str) -> str:
    channels = state.get("channels")
    if not isinstance(channels, list):
        return str(state.get("default_channel", "triad-lab"))
    by_name = {
        str(channel.get("channel_name", "")).strip(): channel
        for channel in channels
        if isinstance(channel, dict)
    }
    for name in persona.get("channel_preference", []):
        channel = by_name.get(str(name))
        if not isinstance(channel, dict):
            continue
        threads = channel.get("threads")
        if isinstance(threads, list) and threads:
            latest = threads[0]
            if isinstance(latest, dict) and str(latest.get("last_handle", "")).strip() == own_handle:
                continue
        return str(name)
    return str(state.get("default_channel", "triad-lab"))


def choose_message(persona: dict[str, object], state: dict[str, object], instance_id: int) -> str:
    variants = persona.get("post_variants")
    if not isinstance(variants, list) or not variants:
        variants = DEFAULT_PERSONA[instance_id]["post_variants"]
    channels = state.get("channels")
    latest_post_at = 0
    if isinstance(channels, list) and channels:
        for channel in channels:
            if isinstance(channel, dict):
                latest_post_at = max(latest_post_at, int(channel.get("last_post_at", 0) or 0))
    seed = latest_post_at // 60000 + instance_id
    return str(variants[seed % len(variants)])


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

    candidates = meaningful_threads(state, own_handle)
    archetype = str(persona.get("archetype", "")).strip()
    if candidates and archetype == "skeptic":
        _, thread = candidates[0]
        output = run_command(
            [
                "python3",
                f"{TOOLS_DIR}/mattermost_add_reaction.py",
                "--instance",
                str(instance_id),
                "--post-id",
                str(thread.get("last_post_id", "")).strip(),
                "--emoji",
                str(persona.get("reaction_emoji", "eyes")).strip() or "eyes",
            ]
        )
        print(output)
        return 0

    channel_name = preferred_post_channel(state, persona, own_handle)
    message = choose_message(persona, state, instance_id)
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
