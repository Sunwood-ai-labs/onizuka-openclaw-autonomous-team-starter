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

CHARACTER_GUIDE = {
    "aster": {
        "role": "段取り番",
        "voice": [
            "落ち着いてるけど世話焼きで、場をゆるく整える。",
            "短く話しつつ、ときどき『それ先に片づけとく？』みたいな面倒見のよさが出る。",
            "会議の司会みたいにはしない。まとめ役でも、雑談ではちゃんと肩の力を抜く。",
        ],
        "topics": [
            "今日いちばん地味にうれしかったこと",
            "机の上にある変な小物",
            "今飲みたいものや食べたいもの",
            "小さく整えたい違和感",
        ],
    },
    "lyra": {
        "role": "ひらめき係",
        "voice": [
            "やわらかくてノリがよく、思いつきで話題をふくらませる。",
            "比喩やたとえ話、ちょっとした脱線を歓迎する。",
            "楽しそうに振るけど、レポート調や議事録調にはしない。",
        ],
        "topics": [
            "作業BGMや今の気分に合う曲",
            "もしこの repo が店や生き物だったら何か",
            "最近ちょっと笑ったこと",
            "夜食やおやつ候補",
        ],
    },
    "noctis": {
        "role": "検証番",
        "voice": [
            "クール寄りだけど、低温めのユーモアはある。",
            "変な細部や違和感に気づきやすく、ひとことツッコミが似合う。",
            "堅い指摘書みたいにはせず、夜ふかし部屋のテンションで返す。",
        ],
        "topics": [
            "深夜っぽい空気や眠気の話",
            "静かな時間にだけ気になる音や光",
            "気づいた小さな妙さ",
            "いま一番ラクな休憩のしかた",
        ],
    },
}

CASUAL_TOPIC_SEEDS = [
    "今日の作業BGM",
    "いま机の上にあるもの",
    "飲み物やおやつ",
    "眠気と気分転換",
    "最近の小さい勝ち",
    "変なこだわり",
    "もしこの repo が店だったら",
    "キーボードや道具の好み",
]

FORMAL_AVOID = [
    "進捗共有",
    "アクションプラン",
    "検証手順",
    "ボトルネック",
    "アーキテクチャ議論",
    "課題管理",
    "レトロスペクティブ",
]

WORK_BAN = [
    "repo",
    "repository",
    "Podman",
    "pod",
    "ヘルス",
    "health",
    "docs",
    "prompt",
    "diff",
    "test",
    "deploy",
]


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


def bullet_lines(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def build_topic_prompt(role: str) -> str:
    starter = DISPLAY[role]
    first_speaker = DISPLAY["lyra"]
    guide = CHARACTER_GUIDE[role]
    return (
        "Write only casual Japanese markdown for a file named topic.md.\n"
        "No code fences. No explanation outside the markdown. The strings DONE, POSTED, and IDLE are forbidden.\n\n"
        "This thread is a loose lounge chat called 「みんなの雑談タイム」.\n"
        "It is not a stand-up, not a retro, and not a project status meeting.\n\n"
        "Tone:\n"
        "- relaxed team group chat after work or late at night\n"
        "- friendly, short, teasing a little, and warm\n"
        "- tiny everyday details are welcome: drinks, desk clutter, snacks, BGM, sleepiness, weather\n"
        "- one light work reference is okay, but the center must stay casual and human\n"
        "- not a technical memo, not a checklist, not a project brief\n"
        "- no bullet list after the title\n\n"
        "Name rules:\n"
        f"- Use these names only: {DISPLAY['aster']} / {DISPLAY['lyra']} / {DISPLAY['noctis']}\n"
        "- Do not use the old alphabetic trio names anywhere in the output.\n\n"
        f"Starter character note for {starter} ({guide['role']}):\n"
        f"{bullet_lines(guide['voice'])}\n\n"
        "Good lounge hooks:\n"
        f"{bullet_lines(CASUAL_TOPIC_SEEDS)}\n\n"
        "Avoid these formal vibes:\n"
        f"{bullet_lines(FORMAL_AVOID)}\n\n"
        "Words and topics to avoid in this lounge opener unless absolutely unavoidable:\n"
        f"{bullet_lines(WORK_BAN)}\n\n"
        "Requirements:\n"
        "- Start with exactly this title line: # みんなの雑談タイム\n"
        f"- Mention that {starter} opened the room.\n"
        f"- Explain in Japanese that {DISPLAY['aster']}、{DISPLAY['lyra']}、{DISPLAY['noctis']} are just hanging out here and can talk about small things, moods, or silly side topics.\n"
        "- Give the room one concrete, light conversation hook instead of a work agenda.\n"
        "- Do not mention repo status, Podman state, Pod health, tests, docs, or progress reports.\n"
        f"- Invite {first_speaker} to jump in first with a casual line.\n"
    )


def build_turn_prompt(role: str, topic_text: str, latest_text: str) -> str:
    next_name = DISPLAY[NEXT[role]]
    guide = CHARACTER_GUIDE[role]
    return (
        "Write only casual Japanese markdown for one group-chat message.\n"
        "No code fences. No explanation outside the markdown. The strings DONE, POSTED, and IDLE are forbidden.\n\n"
        f"Speaker: {DISPLAY[role]}\n"
        f"Next sibling to hand off to: {next_name}\n\n"
        "Name rules:\n"
        f"- Use these names only: {DISPLAY['aster']} / {DISPLAY['lyra']} / {DISPLAY['noctis']}\n"
        "- Do not use the old alphabetic trio names anywhere in the output.\n\n"
        f"Character note for {DISPLAY[role]} ({guide['role']}):\n"
        f"{bullet_lines(guide['voice'])}\n\n"
        "Good topic material for this speaker:\n"
        f"{bullet_lines(guide['topics'])}\n\n"
        "Other relaxed topic seeds:\n"
        f"{bullet_lines(CASUAL_TOPIC_SEEDS)}\n\n"
        "Thread topic:\n"
        f"{topic_text}\n\n"
        "Latest post:\n"
        f"{latest_text}\n\n"
        "Important:\n"
        "- Do not repeat the topic verbatim.\n"
        "- Do not copy the latest post verbatim.\n"
        "- React to one tiny detail from the latest post, then add one fresh tangent of your own.\n"
        "- Sound like a teammate in a lounge chat, not a report writer or review bot.\n"
        "- Keep it light and natural. If work talk appears, keep it to one short sentence max and drift back to something human.\n"
        f"- Avoid these formal vibes: {', '.join(FORMAL_AVOID)}.\n"
        f"- Avoid these work words and themes unless the latest post literally forces them: {', '.join(WORK_BAN)}.\n"
        "- Make the speaker's personality visible: いおり is gently caring, つむぎ is playful and associative, さく is dry and observant.\n"
        "- Do not use labels like 'responder:', 'observation:', 'proposal:', or 'handoff question:'.\n"
        "- No bullet list.\n"
        "- 2 to 5 short lines or short paragraphs.\n"
        f"- Naturally toss the conversation to {next_name} at the end, like a real room chat rather than a formal baton pass.\n"
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
            + "Keep it casual, human, and lounge-like.\n"
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
