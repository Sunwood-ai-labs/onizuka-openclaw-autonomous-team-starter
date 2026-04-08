#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


MANAGED_MARKER = "<!-- Managed by openclaw-podman-starter: shared board scaffold -->"
BOARD_ROOT = Path("/home/node/.openclaw/shared-board")
THREAD_DIR = BOARD_ROOT / "threads" / "background-lounge"
TOPIC_PATH = THREAD_DIR / "topic.md"
VIEWER_SCRIPT = BOARD_ROOT / "tools" / "render_board_view.py"

DISPLAY = {
    "aster": "いおり",
    "lyra": "つむぎ",
    "noctis": "さく",
}

PREVIOUS = {
    "aster": "noctis",
    "lyra": "aster",
    "noctis": "lyra",
}

NEXT = {
    "aster": "lyra",
    "lyra": "noctis",
    "noctis": "aster",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One autochat turn for the shared board.")
    parser.add_argument("--role", choices=sorted(DISPLAY), required=True)
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def run_openclaw(prompt: str, session_id: str, timeout_seconds: int, agent_id: str) -> tuple[str, dict[str, object]]:
    command = [
        "openclaw",
        "agent",
        "--local",
        "--agent",
        agent_id,
        "--thinking",
        "off",
        "--timeout",
        str(timeout_seconds),
        "--json",
        "--session-id",
        session_id,
        "--message",
        prompt,
    ]
    env = dict(os.environ)
    env.pop("OPENCLAW_CONTAINER", None)
    env.pop("OPENCLAW_PODMAN_CONTAINER", None)

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "openclaw agent failed\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )

    outputs = [completed.stdout.strip(), completed.stderr.strip()]
    outputs = [output for output in outputs if output]
    if not outputs:
        raise RuntimeError("openclaw agent returned no output")

    payload: dict[str, object] | None = None
    for output in outputs:
        try:
            payload = json.loads(output)
            break
        except json.JSONDecodeError:
            start = output.find("{")
            if start >= 0:
                try:
                    payload = json.loads(output[start:])
                    break
                except json.JSONDecodeError:
                    continue
    if payload is None:
        raise RuntimeError(
            "openclaw agent returned non-JSON output\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )

    payloads = payload.get("payloads")
    texts: list[str] = []
    if isinstance(payloads, list):
        for entry in payloads:
            if isinstance(entry, dict):
                text = entry.get("text")
                if isinstance(text, str):
                    texts.append(text.strip())
    return "\n".join(text for text in texts if text).strip(), payload


def clean_markdown(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def looks_like_status_text(text: str) -> bool:
    normalized = text.strip().upper()
    return normalized in {"DONE", "POSTED", "IDLE"}


def latest_turn_file() -> Path | None:
    turn_files = sorted(THREAD_DIR.glob("turn-*.md"), key=lambda path: path.stat().st_mtime)
    return turn_files[-1] if turn_files else None


def latest_speaker_slug() -> str | None:
    latest = latest_turn_file()
    if latest is None:
        if TOPIC_PATH.exists():
            return "aster"
        return None
    parts = latest.stem.split("-")
    if len(parts) >= 3 and parts[0] == "turn":
        return parts[1]
    return None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")


def turn_path(role: str, stamp: str) -> Path:
    return THREAD_DIR / f"turn-{role}-{stamp}.md"


def build_topic_prompt(role: str) -> str:
    starter = DISPLAY[role]
    first_speaker = DISPLAY["lyra"]
    return (
        "Write only casual Japanese markdown for a file named topic.md.\n"
        "No code fences. No explanation outside the markdown. The strings DONE, POSTED, and IDLE are forbidden.\n\n"
        "Tone:\n"
        "- relaxed team group chat\n"
        "- friendly, short, a little playful\n"
        "- not a technical memo\n"
        "- no bullet list after the title\n\n"
        "Name rules:\n"
        f"- Use these names only: {DISPLAY['aster']} / {DISPLAY['lyra']} / {DISPLAY['noctis']}\n"
        "- Do not use Aster, Lyra, or Noctis anywhere in the output.\n\n"
        "Requirements:\n"
        "- Start with a chat-room style title line.\n"
        f"- Mention that {starter} opened the room.\n"
        f"- Explain in Japanese that {DISPLAY['aster']}、{DISPLAY['lyra']}、{DISPLAY['noctis']} are hanging out here and can casually talk about what they are noticing.\n"
        f"- Invite {first_speaker} to jump in first.\n"
    )


def build_turn_prompt(role: str, topic_text: str, latest_text: str) -> str:
    next_name = DISPLAY[NEXT[role]]
    return (
        "Write only casual Japanese markdown for one group-chat message.\n"
        "No code fences. No explanation outside the markdown. The strings DONE, POSTED, and IDLE are forbidden.\n\n"
        f"Speaker: {DISPLAY[role]}\n"
        f"Next sibling to hand off to: {next_name}\n\n"
        "Name rules:\n"
        f"- Use these names only: {DISPLAY['aster']} / {DISPLAY['lyra']} / {DISPLAY['noctis']}\n"
        "- Do not use Aster, Lyra, or Noctis anywhere in the output.\n\n"
        "Thread topic:\n"
        f"{topic_text}\n\n"
        "Latest post:\n"
        f"{latest_text}\n\n"
        "Important:\n"
        "- Do not repeat the topic verbatim.\n"
        "- Do not copy the latest post verbatim.\n"
        "- Sound like a teammate in a lounge chat, not a report writer.\n"
        "- Keep it light and natural, but still grounded in what just happened.\n"
        "- Do not use labels like 'responder:', 'observation:', 'proposal:', or 'handoff question:'.\n"
        "- No bullet list.\n"
        "- 2 to 5 short lines or short paragraphs.\n"
        f"- Naturally toss the conversation to {next_name} at the end.\n"
    )


def generate_markdown(prompt: str, session_id: str, timeout_seconds: int, agent_id: str) -> str:
    current_prompt = prompt
    for attempt in range(2):
        text, payload = run_openclaw(current_prompt, session_id, timeout_seconds, agent_id)
        markdown = clean_markdown(text)
        if markdown and not looks_like_status_text(markdown):
            return markdown
        current_prompt = (
            prompt
            + "\n\nYour previous response was invalid because it was only a status word.\n"
            + "Return only the markdown body. Do not say DONE, POSTED, or IDLE.\n"
            + "Keep it casual and chat-like.\n"
            + "Do not use report labels or bullet points.\n"
            + "Write at least 2 non-empty lines.\n"
        )
    raise RuntimeError(f"markdown generation returned only status text: {json.dumps(payload, ensure_ascii=False, indent=2)}")


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def refresh_viewer() -> None:
    completed = subprocess.run(
        ["python3", str(VIEWER_SCRIPT), "--board-root", str(BOARD_ROOT)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "viewer render failed\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def create_topic(role: str, timeout_seconds: int) -> str:
    prompt = build_topic_prompt(role)
    markdown = generate_markdown(prompt, f"background-lounge-topic-{role}", timeout_seconds, f"autochat-{role}")
    write_file(TOPIC_PATH, markdown)
    refresh_viewer()
    return f"POSTED {TOPIC_PATH.name}"


def create_turn(role: str, timeout_seconds: int) -> str:
    latest = latest_turn_file()
    latest_text = read_text(latest) if latest is not None else read_text(TOPIC_PATH)
    prompt = build_turn_prompt(role, read_text(TOPIC_PATH), latest_text)
    markdown = generate_markdown(prompt, f"background-lounge-turn-{role}-{timestamp_slug()}", timeout_seconds, f"autochat-{role}")
    path = turn_path(role, timestamp_slug())
    write_file(path, markdown)
    refresh_viewer()
    return f"POSTED {path.name}"


def main() -> int:
    args = parse_args()
    role = args.role

    THREAD_DIR.mkdir(parents=True, exist_ok=True)
    latest_role = latest_speaker_slug()

    if not TOPIC_PATH.exists():
        if role != "aster":
            print("IDLE no-topic")
            return 0
        print(create_topic(role, args.timeout))
        return 0

    if latest_role != PREVIOUS[role]:
        print(f"IDLE latest={latest_role}")
        return 0

    print(create_turn(role, args.timeout))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - runtime diagnostic path
        print(f"ERROR {exc}", file=sys.stderr)
        raise
