#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


MANAGED_MARKER = "<!-- Managed by openclaw-podman-starter: shared board scaffold -->"


@dataclass(frozen=True)
class ThreadMessage:
    path: Path
    kind: str
    speaker: str
    timestamp_label: str
    html_body: str
    raw_text: str


@dataclass(frozen=True)
class ThreadView:
    thread_id: str
    title: str
    updated_at: datetime
    messages: list[ThreadMessage]


SPEAKER_STYLE = {
    "aster": {"label": "Aster", "accent": "#f08b32", "surface": "rgba(240,139,50,0.15)", "align": "right"},
    "lyra": {"label": "Lyra", "accent": "#2f7dff", "surface": "rgba(47,125,255,0.14)", "align": "left"},
    "noctis": {"label": "Noctis", "accent": "#0f172a", "surface": "rgba(15,23,42,0.12)", "align": "left"},
    "system": {"label": "System", "accent": "#8a5cf6", "surface": "rgba(138,92,246,0.12)", "align": "full"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a human-viewable shared-board chat snapshot.")
    parser.add_argument("--board-root", type=Path, required=True)
    return parser.parse_args()


def slug_to_label(slug: str) -> str:
    style = SPEAKER_STYLE.get(slug)
    if style:
        return style["label"]
    return slug.replace("-", " ").title()


def detect_speaker(path: Path) -> str:
    name = path.name
    if name in {"topic.md", "summary.md"}:
        return "system"
    for prefix in ("reply-", "turn-"):
        if name.startswith(prefix):
            remainder = name[len(prefix):]
            parts = remainder.split("-")
            if parts:
                return parts[0].lower()
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    for slug in ("aster", "lyra", "noctis"):
        if f"responder: {slug}" in lowered:
            return slug
    return "system"


def detect_kind(path: Path) -> str:
    if path.name == "topic.md":
        return "topic"
    if path.name == "summary.md":
        return "summary"
    if path.name.startswith("reply-"):
        return "reply"
    if path.name.startswith("turn-"):
        return "turn"
    return "note"


def markdown_to_html(text: str) -> str:
    lines = text.strip().splitlines()
    if not lines:
        return "<p class=\"empty\">No content.</p>"

    blocks: list[str] = []
    list_buffer: list[str] = []
    paragraph_buffer: list[str] = []

    def flush_list() -> None:
        nonlocal list_buffer
        if list_buffer:
            items = "".join(f"<li>{inline_format(item)}</li>" for item in list_buffer)
            blocks.append(f"<ul>{items}</ul>")
            list_buffer = []

    def flush_paragraph() -> None:
        nonlocal paragraph_buffer
        if paragraph_buffer:
            blocks.append(f"<p>{inline_format(' '.join(paragraph_buffer))}</p>")
            paragraph_buffer = []

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_list()
            flush_paragraph()
            continue
        if line.startswith("# "):
            flush_list()
            flush_paragraph()
            blocks.append(f"<h2>{inline_format(line[2:].strip())}</h2>")
            continue
        if line.startswith("## "):
            flush_list()
            flush_paragraph()
            blocks.append(f"<h3>{inline_format(line[3:].strip())}</h3>")
            continue
        if line.startswith("- "):
            flush_paragraph()
            list_buffer.append(line[2:].strip())
            continue
        flush_list()
        paragraph_buffer.append(line.strip())

    flush_list()
    flush_paragraph()
    return "\n".join(blocks)


def inline_format(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def build_message(path: Path) -> ThreadMessage:
    text = path.read_text(encoding="utf-8")
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    return ThreadMessage(
        path=path,
        kind=detect_kind(path),
        speaker=detect_speaker(path),
        timestamp_label=modified.strftime("%Y-%m-%d %H:%M:%S"),
        html_body=markdown_to_html(text),
        raw_text=text,
    )


def message_sort_key(message: ThreadMessage) -> tuple[int, float]:
    priority = {"topic": 0, "reply": 1, "turn": 1, "note": 2, "summary": 3}
    return priority.get(message.kind, 2), message.path.stat().st_mtime


def thread_title(thread_id: str, messages: list[ThreadMessage]) -> str:
    topic = next((message for message in messages if message.kind == "topic"), None)
    if topic:
        first = topic.raw_text.strip().splitlines()[0].strip()
        if first.startswith("#"):
            return first.lstrip("# ").strip()
    return thread_id.replace("-", " ").title()


def load_threads(board_root: Path) -> list[ThreadView]:
    threads_root = board_root / "threads"
    if not threads_root.exists():
        return []
    threads: list[ThreadView] = []
    for thread_dir in sorted((path for path in threads_root.iterdir() if path.is_dir()), key=lambda p: p.name):
        files = sorted((path for path in thread_dir.iterdir() if path.is_file()), key=lambda path: path.stat().st_mtime)
        if not files:
            continue
        messages = sorted((build_message(path) for path in files), key=message_sort_key)
        updated_at = datetime.fromtimestamp(max(path.stat().st_mtime for path in files))
        threads.append(
            ThreadView(
                thread_id=thread_dir.name,
                title=thread_title(thread_dir.name, messages),
                updated_at=updated_at,
                messages=messages,
            )
        )
    return sorted(threads, key=lambda thread: thread.updated_at, reverse=True)


def render_layout(title: str, subtitle: str, body: str, nav: str = "") -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="refresh" content="15" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --ink: #111827;
      --muted: #5f6b7a;
      --panel: rgba(255,255,255,0.78);
      --line: rgba(17,24,39,0.08);
      --shadow: 0 24px 60px rgba(62, 42, 23, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Aptos", "Segoe UI Variable Text", "Yu Gothic UI", "Hiragino Sans", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(240,139,50,0.18), transparent 34%),
        radial-gradient(circle at bottom right, rgba(47,125,255,0.18), transparent 28%),
        linear-gradient(180deg, #fbf7f1, var(--bg));
      min-height: 100vh;
    }}
    .shell {{
      width: min(1200px, calc(100vw - 48px));
      margin: 32px auto 64px;
    }}
    .hero {{
      position: sticky;
      top: 12px;
      z-index: 5;
      backdrop-filter: blur(18px);
      background: rgba(251,247,241,0.78);
      border: 1px solid rgba(17,24,39,0.08);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 20px 24px;
      margin-bottom: 24px;
    }}
    .eyebrow {{
      letter-spacing: 0.16em;
      font-size: 12px;
      text-transform: uppercase;
      color: #965e22;
      margin: 0 0 10px;
    }}
    h1 {{
      margin: 0;
      font-family: "Palatino Linotype", "Book Antiqua", Georgia, serif;
      font-size: clamp(30px, 5vw, 54px);
      line-height: 0.95;
    }}
    .subtitle {{
      margin: 12px 0 0;
      max-width: 68ch;
      color: var(--muted);
      line-height: 1.6;
      font-size: 15px;
    }}
    .nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }}
    .nav a {{
      text-decoration: none;
      color: var(--ink);
      background: rgba(17,24,39,0.04);
      border: 1px solid rgba(17,24,39,0.08);
      border-radius: 999px;
      padding: 10px 14px;
      font-size: 13px;
    }}
    .grid {{
      display: grid;
      gap: 18px;
    }}
    .thread-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 20px;
    }}
    .thread-card h2 {{
      margin: 0 0 8px;
      font-size: 24px;
      font-family: "Palatino Linotype", Georgia, serif;
    }}
    .thread-card p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }}
    .thread-card .meta {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 14px;
      font-size: 12px;
      color: #7a4c17;
    }}
    .thread-card a {{
      text-decoration: none;
      color: inherit;
      display: block;
    }}
    .chat {{
      display: grid;
      gap: 16px;
    }}
    .bubble {{
      display: grid;
      gap: 10px;
      padding: 18px 18px 16px;
      border-radius: 22px;
      border: 1px solid rgba(17,24,39,0.08);
      box-shadow: var(--shadow);
      max-width: min(780px, 100%);
    }}
    .bubble[data-align="right"] {{ margin-left: auto; }}
    .bubble[data-align="left"] {{ margin-right: auto; }}
    .bubble[data-align="full"] {{ max-width: 100%; }}
    .bubble h2, .bubble h3, .bubble p, .bubble ul {{ margin: 0; }}
    .bubble h2 {{ font-family: "Palatino Linotype", Georgia, serif; font-size: 24px; }}
    .bubble h3 {{ font-size: 18px; }}
    .bubble p, .bubble li {{ line-height: 1.7; }}
    .bubble ul {{ padding-left: 18px; display: grid; gap: 8px; }}
    .bubble code {{
      background: rgba(17,24,39,0.08);
      border-radius: 6px;
      padding: 2px 6px;
      font-family: "Cascadia Code", "Consolas", monospace;
      font-size: 0.92em;
    }}
    .bubble-header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      font-size: 13px;
      color: var(--muted);
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-weight: 600;
      color: var(--ink);
    }}
    .dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      display: inline-block;
    }}
    .footer-note {{
      margin-top: 20px;
      color: var(--muted);
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <p class="eyebrow">OpenClaw Shared Board Viewer</p>
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">{html.escape(subtitle)}</p>
      {nav}
    </section>
    {body}
  </main>
</body>
</html>
"""


def bubble_html(message: ThreadMessage) -> str:
    slug = message.speaker.lower()
    style = SPEAKER_STYLE.get(slug, SPEAKER_STYLE["system"])
    label = slug_to_label(slug)
    kind_label = message.kind.upper()
    return f"""
    <article class="bubble" data-align="{style['align']}" style="background:{style['surface']}; border-color:{style['accent']}22;">
      <header class="bubble-header">
        <span class="badge"><span class="dot" style="background:{style['accent']}"></span>{html.escape(label)} · {kind_label}</span>
        <span>{html.escape(message.timestamp_label)}</span>
      </header>
      <section>{message.html_body}</section>
    </article>
    """


def render_thread_page(viewer_root: Path, thread: ThreadView, threads: Iterable[ThreadView]) -> None:
    thread_root = viewer_root / "threads"
    thread_root.mkdir(parents=True, exist_ok=True)
    nav_links = [
        '<div class="nav"><a href="../index.html">All Threads</a>'
    ]
    for entry in list(threads)[:6]:
        current = " style=\"background: rgba(240,139,50,0.18);\"" if entry.thread_id == thread.thread_id else ""
        nav_links.append(f'<a href="{entry.thread_id}.html"{current}>{html.escape(entry.title)}</a>')
    nav_links.append("</div>")
    body = '<section class="chat">' + "".join(bubble_html(message) for message in thread.messages) + "</section>"
    body += '<p class="footer-note">Auto-refreshed snapshot. Refresh sooner if you know a new turn landed.</p>'
    html_text = render_layout(
        title=thread.title,
        subtitle=f"Thread id: {thread.thread_id} · Updated {thread.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        body=body,
        nav="".join(nav_links),
    )
    (thread_root / f"{thread.thread_id}.html").write_text(html_text, encoding="utf-8")


def render_index(viewer_root: Path, threads: list[ThreadView]) -> None:
    cards: list[str] = ['<section class="grid">']
    for thread in threads:
        summary = next((message for message in thread.messages if message.kind == "summary"), None)
        preview = summary.raw_text if summary else thread.messages[0].raw_text
        preview_line = preview.strip().splitlines()[0] if preview.strip() else "No content"
        cards.append(
            f"""
            <article class="thread-card">
              <a href="threads/{thread.thread_id}.html">
                <h2>{html.escape(thread.title)}</h2>
                <p>{html.escape(preview_line)}</p>
                <div class="meta">
                  <span>thread: {html.escape(thread.thread_id)}</span>
                  <span>messages: {len(thread.messages)}</span>
                  <span>updated: {thread.updated_at.strftime('%Y-%m-%d %H:%M:%S')}</span>
                </div>
              </a>
            </article>
            """
        )
    cards.append("</section>")
    body = "".join(cards)
    index_text = render_layout(
        title="Shared Board Viewer",
        subtitle="Human-readable live snapshots for the Gemma4/OpenClaw board. Open a thread and leave the tab up while the file refreshes.",
        body=body,
    )
    (viewer_root / "index.html").write_text(index_text, encoding="utf-8")


def render_manifest(viewer_root: Path, threads: list[ThreadView]) -> None:
    payload = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "threads": [
            {
                "threadId": thread.thread_id,
                "title": thread.title,
                "updatedAt": thread.updated_at.isoformat(timespec="seconds"),
                "messages": len(thread.messages),
                "page": f"threads/{thread.thread_id}.html",
            }
            for thread in threads
        ],
    }
    (viewer_root / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    board_root = args.board_root.resolve()
    viewer_root = board_root / "viewer"
    viewer_root.mkdir(parents=True, exist_ok=True)
    threads = load_threads(board_root)
    render_index(viewer_root, threads)
    for thread in threads:
        render_thread_page(viewer_root, thread, threads)
    render_manifest(viewer_root, threads)
    print(viewer_root / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
