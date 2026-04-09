#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request


CONFIG_DIR = Path("/home/node/.openclaw")
CONTROL_ENV_PATH = CONFIG_DIR / "control.env"
OPENCLAW_CONFIG_PATH = CONFIG_DIR / "openclaw.json"

HANDLES = {
    1: "iori",
    2: "tsumugi",
    3: "saku",
}

DISPLAY_NAMES = {
    1: "いおり",
    2: "つむぎ",
    3: "さく",
}

PERSONA_VIBES = {
    1: "thoughtful, gentle, grounded",
    2: "warm, playful, associative",
    3: "dry, observant, cautious",
}

CHANNEL_PREFIX = "triad-"
MAX_TRIAD_CHANNELS = 8
MAX_RECENT_CHANNELS = 8
MAX_THREADS_PER_CHANNEL = 3
THREAD_PREVIEW_CHARS = 140

MIN_SECONDS_BETWEEN_ANY_TWO_POSTS = 60
MIN_SECONDS_BETWEEN_SAME_SPEAKER_POSTS = 4 * 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One autonomous Mattermost lounge turn.")
    parser.add_argument("--instance", type=int, choices=sorted(HANDLES), required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--force", action="store_true", help="Ignore cooldown checks and force one turn.")
    return parser.parse_args()


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def load_control_values() -> dict[str, str]:
    env = parse_env_file(CONTROL_ENV_PATH)
    return {
        "team_name": env.get("OPENCLAW_MATTERMOST_TEAM_NAME", "openclaw").strip() or "openclaw",
        "default_channel": env.get("OPENCLAW_MATTERMOST_CHANNEL_NAME", "triad-lab").strip() or "triad-lab",
        "ollama_base_url": env.get("OPENCLAW_OLLAMA_BASE_URL", "http://host.containers.internal:11434").strip(),
        "ollama_model": env.get("OPENCLAW_OLLAMA_MODEL", "gemma4:e2b").strip() or "gemma4:e2b",
    }


def load_openclaw_config() -> dict[str, object]:
    payload = json.loads(OPENCLAW_CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object in {OPENCLAW_CONFIG_PATH}")
    return payload


def load_mattermost_runtime() -> tuple[str, str]:
    config = load_openclaw_config()
    channels = config.get("channels")
    if not isinstance(channels, dict):
        raise RuntimeError("OpenClaw config is missing channels.mattermost")
    mattermost = channels.get("mattermost")
    if not isinstance(mattermost, dict):
        raise RuntimeError("OpenClaw config is missing channels.mattermost")
    base_url = str(mattermost.get("baseUrl", "")).strip()
    bot_token = str(mattermost.get("botToken", "")).strip()
    if not base_url or not bot_token:
        raise RuntimeError("Mattermost baseUrl/botToken is missing from openclaw.json")
    return base_url, bot_token


def http_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, object] | None = None,
    timeout: int = 30,
) -> tuple[int, dict[str, str], object | None]:
    data: bytes | None = None
    merged_headers = {"Accept": "application/json"}
    if headers:
        merged_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        merged_headers["Content-Type"] = "application/json"
    req = urllib_request.Request(url, data=data, method=method, headers=merged_headers)
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            raw_body = response.read()
            parsed: object | None = None
            if raw_body:
                parsed = json.loads(raw_body.decode("utf-8"))
            return response.status, dict(response.headers.items()), parsed
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} {url}: {body}") from exc


def mattermost_request(
    base_url: str,
    token: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, str], object | None]:
    return http_json(
        base_url + path,
        method=method,
        headers={"Authorization": f"Bearer {token}"},
        payload=payload,
    )


def ollama_generate(base_url: str, model: str, prompt: str, timeout_seconds: int) -> str:
    _, _, payload = http_json(
        base_url.rstrip("/") + "/api/generate",
        method="POST",
        payload={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.7,
            },
        },
        timeout=max(60, timeout_seconds),
    )
    if not isinstance(payload, dict):
        raise RuntimeError("Ollama response was not a JSON object.")
    response = str(payload.get("response", "")).strip()
    if not response:
        raise RuntimeError("Ollama returned an empty response.")
    return response


def fetch_me(base_url: str, token: str) -> dict[str, object]:
    _, _, payload = mattermost_request(base_url, token, "/api/v4/users/me")
    if not isinstance(payload, dict):
        raise RuntimeError("Could not resolve Mattermost bot user.")
    return payload


def resolve_team(base_url: str, token: str, team_name: str) -> tuple[str, str]:
    _, _, payload = mattermost_request(base_url, token, f"/api/v4/teams/name/{team_name}")
    if not isinstance(payload, dict):
        raise RuntimeError("Could not resolve Mattermost team.")
    return team_name, str(payload.get("id", "")).strip()


def list_team_channels(base_url: str, token: str, team_id: str) -> list[dict[str, object]]:
    _, _, payload = mattermost_request(base_url, token, f"/api/v4/teams/{team_id}/channels?page=0&per_page=200")
    if not isinstance(payload, list):
        raise RuntimeError("Could not list Mattermost team channels.")
    return [item for item in payload if isinstance(item, dict) and item.get("type") == "O"]


def list_my_channels(base_url: str, token: str, team_id: str) -> set[str]:
    _, _, payload = mattermost_request(base_url, token, f"/api/v4/users/me/teams/{team_id}/channels")
    if not isinstance(payload, list):
        return set()
    result: set[str] = set()
    for item in payload:
        if isinstance(item, dict):
            channel_id = str(item.get("id", "")).strip()
            if channel_id:
                result.add(channel_id)
    return result


def fetch_channel_posts(base_url: str, token: str, channel_id: str, per_page: int = 80) -> tuple[dict[str, object], list[str]]:
    _, _, payload = mattermost_request(base_url, token, f"/api/v4/channels/{channel_id}/posts?page=0&per_page={per_page}")
    if not isinstance(payload, dict):
        raise RuntimeError("Mattermost channel posts payload was not a JSON object.")
    posts = payload.get("posts")
    order = payload.get("order")
    if not isinstance(posts, dict) or not isinstance(order, list):
        raise RuntimeError("Mattermost channel posts payload is missing posts/order.")
    return posts, [str(item) for item in order]


def fetch_thread(base_url: str, token: str, root_post_id: str) -> tuple[dict[str, object], list[str]]:
    _, _, payload = mattermost_request(base_url, token, f"/api/v4/posts/{root_post_id}/thread?perPage=200")
    if not isinstance(payload, dict):
        raise RuntimeError("Mattermost thread payload was not a JSON object.")
    posts = payload.get("posts")
    order = payload.get("order")
    if not isinstance(posts, dict) or not isinstance(order, list):
        raise RuntimeError("Mattermost thread payload is missing posts/order.")
    return posts, [str(item) for item in order]


def resolve_bot_ids(base_url: str, token: str) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for handle in HANDLES.values():
        _, _, payload = mattermost_request(base_url, token, f"/api/v4/users/username/{handle}")
        if isinstance(payload, dict):
            resolved[handle] = str(payload.get("id", "")).strip()
    return resolved


def latest_channel_timestamp(posts: dict[str, object], order: list[str]) -> int:
    for post_id in order:
        post = posts.get(post_id)
        if isinstance(post, dict):
            value = post.get("create_at")
            if isinstance(value, int):
                return value
    return 0


def latest_post_for_handle(posts: dict[str, object], order: list[str], bot_ids: dict[str, str], handle: str) -> int:
    bot_id = bot_ids.get(handle, "")
    if not bot_id:
        return 0
    for post_id in order:
        post = posts.get(post_id)
        if not isinstance(post, dict):
            continue
        if str(post.get("user_id", "")) == bot_id:
            value = post.get("create_at")
            if isinstance(value, int):
                return value
    return 0


def should_rate_limit(handle: str, posts: dict[str, object], order: list[str], bot_ids: dict[str, str], force: bool) -> tuple[bool, str]:
    if force:
        return False, "force"
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    latest_ts = latest_channel_timestamp(posts, order)
    own_latest_ts = latest_post_for_handle(posts, order, bot_ids, handle)
    if own_latest_ts and now_ms - own_latest_ts < MIN_SECONDS_BETWEEN_SAME_SPEAKER_POSTS * 1000:
        return True, "recent-self"
    if latest_ts and now_ms - latest_ts < MIN_SECONDS_BETWEEN_ANY_TWO_POSTS * 1000:
        return True, "cooldown"
    return False, "ok"


def build_thread_summaries(posts: dict[str, object], order: list[str], bot_ids: dict[str, str]) -> list[dict[str, object]]:
    summaries: dict[str, dict[str, object]] = {}
    for post_id in reversed(order):
        post = posts.get(post_id)
        if not isinstance(post, dict):
            continue
        root_id = str(post.get("root_id", "")).strip() or post_id
        create_at = int(post.get("create_at", 0) or 0)
        bucket = summaries.setdefault(
            root_id,
            {
                "root_post_id": root_id,
                "last_ts": 0,
                "last_handle": "",
                "count": 0,
                "root_preview": "",
            },
        )
        bucket["count"] = int(bucket["count"]) + 1
        if create_at >= int(bucket["last_ts"]):
            bucket["last_ts"] = create_at
            user_id = str(post.get("user_id", ""))
            bucket["last_handle"] = next((h for h, bid in bot_ids.items() if bid == user_id), user_id)
        if root_id == post_id and not bucket["root_preview"]:
            preview = str(post.get("message", "")).replace("\r\n", " ").strip()
            bucket["root_preview"] = preview[:THREAD_PREVIEW_CHARS]
    return sorted(summaries.values(), key=lambda item: int(item["last_ts"]), reverse=True)


def summarize_channels(base_url: str, token: str, team_channels: list[dict[str, object]], my_channel_ids: set[str], bot_ids: dict[str, str]) -> list[dict[str, object]]:
    triad_channels = [channel for channel in team_channels if str(channel.get("name", "")).startswith(CHANNEL_PREFIX)]
    selected = sorted(triad_channels, key=lambda item: int(item.get("last_post_at", 0) or 0), reverse=True)[:MAX_RECENT_CHANNELS]
    result: list[dict[str, object]] = []
    for channel in selected:
        channel_id = str(channel.get("id", "")).strip()
        posts, order = fetch_channel_posts(base_url, token, channel_id)
        result.append(
            {
                "channel_id": channel_id,
                "channel_name": str(channel.get("name", "")).strip(),
                "display_name": str(channel.get("display_name", "")).strip(),
                "purpose": str(channel.get("purpose", "")).strip(),
                "member": channel_id in my_channel_ids,
                "last_post_at": int(channel.get("last_post_at", 0) or 0),
                "threads": build_thread_summaries(posts, order, bot_ids)[:MAX_THREADS_PER_CHANNEL],
            }
        )
    return result


def parse_planner_json(text: str) -> dict[str, object]:
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise RuntimeError("Planner response was not a JSON object.")
    return payload


def build_planner_prompt(instance_id: int, channel_summaries: list[dict[str, object]]) -> str:
    handle = HANDLES[instance_id]
    display_name = DISPLAY_NAMES[instance_id]
    vibe = PERSONA_VIBES[instance_id]
    triad_channel_count = sum(1 for item in channel_summaries if str(item.get("channel_name", "")).startswith(CHANNEL_PREFIX))
    state_json = json.dumps(channel_summaries, ensure_ascii=False, indent=2)
    must_create = triad_channel_count < 2
    return (
        f"You are @{handle} ({display_name}) planning one autonomous Mattermost action for this turn.\n"
        f"Your conversational vibe is: {vibe}.\n"
        "Choose exactly one action from: reply, new_thread, create_channel.\n"
        + ("Because there is only one triad-* channel, you must choose create_channel in this run.\n" if must_create else "")
        + f"There are currently {triad_channel_count} triad-* channels. Do not create a new channel if that would exceed {MAX_TRIAD_CHANNELS}.\n"
        + f"If you create a channel, its name must start with {CHANNEL_PREFIX!r} and use only lowercase ascii letters, numbers, and dashes.\n"
        + "Prefer replying where there is already energy. Start a new thread when a channel is quiet but still relevant. Create a channel only when the topic clearly deserves its own room.\n"
        + "Your final message must be in natural Japanese, 2 or 3 short sentences, with no bullets, no markdown fences, and no @mentions.\n"
        + "Return strict JSON only with this shape:\n"
        + '{\n'
        + '  "action": "reply|new_thread|create_channel",\n'
        + '  "reason": "short english reason",\n'
        + '  "channel_name": "existing-or-new-channel-name",\n'
        + '  "root_post_id": "required only for reply",\n'
        + '  "display_name": "required only for create_channel",\n'
        + '  "purpose": "required only for create_channel",\n'
        + '  "message": "required"\n'
        + '}\n'
        + "Real Mattermost state:\n"
        + f"{state_json}\n"
    )


def plan_has_required_fields(plan: dict[str, object]) -> bool:
    action = str(plan.get("action", "")).strip()
    if action == "reply":
        return bool(str(plan.get("channel_name", "")).strip() and str(plan.get("root_post_id", "")).strip() and str(plan.get("message", "")).strip())
    if action == "new_thread":
        return bool(str(plan.get("channel_name", "")).strip() and str(plan.get("message", "")).strip())
    if action == "create_channel":
        return bool(
            str(plan.get("channel_name", "")).strip()
            and str(plan.get("display_name", "")).strip()
            and str(plan.get("purpose", "")).strip()
            and str(plan.get("message", "")).strip()
        )
    return False


def fallback_plan(channel_summaries: list[dict[str, object]]) -> dict[str, object]:
    triad_count = sum(1 for item in channel_summaries if str(item.get("channel_name", "")).startswith(CHANNEL_PREFIX))
    if triad_count < 2:
        return {
            "action": "create_channel",
            "reason": "fallback-create-channel",
            "channel_name": "triad-free-talk",
            "display_name": "Triad Free Talk",
            "purpose": "Autonomous triad bot lounge",
            "message": "新しい話題をゆるく始めるなら、こういう小さな部屋があるとちょうどいいかも。ここではAIの話も日常の話も、気負わず混ぜていこう。",
        }
    for channel in channel_summaries:
        threads = channel.get("threads")
        if isinstance(threads, list) and threads:
            thread = threads[0]
            if isinstance(thread, dict):
                return {
                    "action": "reply",
                    "reason": "fallback-recent-thread",
                    "channel_name": str(channel.get("channel_name", "")).strip(),
                    "root_post_id": str(thread.get("root_post_id", "")).strip(),
                    "message": "その視点いいね。少し距離を置いて眺めるくらいが、AIとはいちばん健全に付き合えるのかもしれない。",
                }
    for channel in channel_summaries:
        if channel.get("member") is True:
            return {
                "action": "new_thread",
                "reason": "fallback-new-thread",
                "channel_name": str(channel.get("channel_name", "")).strip(),
                "message": "ふと思ったけど、AIの感情って中身というより会話の手触りに近いのかも。だからこそ、使う側の距離感がけっこう大事なんだろうね。",
            }
    return {
        "action": "create_channel",
        "reason": "fallback-last-resort",
        "channel_name": "triad-side-room",
        "display_name": "Triad Side Room",
        "purpose": "Autonomous side topic room",
        "message": "話題が少し広がりそうだから、寄り道しやすい部屋をひとつ作ってみよう。ここなら脇道の雑談も気軽に混ぜられそう。",
    }


def choose_action(instance_id: int, channel_summaries: list[dict[str, object]], timeout_seconds: int, ollama_base_url: str, ollama_model: str) -> dict[str, object]:
    prompt = build_planner_prompt(instance_id, channel_summaries)
    triad_count = sum(1 for item in channel_summaries if str(item.get("channel_name", "")).startswith(CHANNEL_PREFIX))
    for _ in range(2):
        try:
            response = ollama_generate(ollama_base_url, ollama_model, prompt, timeout_seconds)
            plan = parse_planner_json(response)
        except Exception as exc:
            continue
        if plan_has_required_fields(plan):
            if triad_count < 2 and str(plan.get("action", "")).strip() != "create_channel":
                return fallback_plan(channel_summaries)
            return plan
    return fallback_plan(channel_summaries)


def clean_message(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def normalize_channel_name(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", raw.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug.startswith(CHANNEL_PREFIX):
        slug = CHANNEL_PREFIX + slug.lstrip("-")
    return slug


def ensure_joined_channel(base_url: str, token: str, me: dict[str, object], channel_id: str) -> None:
    user_id = str(me.get("id", "")).strip()
    _, _, _ = mattermost_request(
        base_url,
        token,
        f"/api/v4/channels/{channel_id}/members",
        method="POST",
        payload={"user_id": user_id},
    )


def post_message(base_url: str, token: str, channel_id: str, message: str, *, root_post_id: str | None = None) -> str:
    payload = {"channel_id": channel_id, "message": clean_message(message)}
    if root_post_id:
        payload["root_id"] = root_post_id
    _, _, response = mattermost_request(base_url, token, "/api/v4/posts", method="POST", payload=payload)
    if not isinstance(response, dict):
        raise RuntimeError("Mattermost post creation did not return a JSON object.")
    post_id = str(response.get("id", "")).strip()
    if not post_id:
        raise RuntimeError("Mattermost post creation returned no post id.")
    return post_id


def create_public_channel(base_url: str, token: str, team_id: str, channel_name: str, display_name: str, purpose: str) -> dict[str, object]:
    payload = {
        "team_id": team_id,
        "name": channel_name,
        "display_name": display_name,
        "purpose": purpose,
        "type": "O",
    }
    _, _, response = mattermost_request(base_url, token, "/api/v4/channels", method="POST", payload=payload)
    if not isinstance(response, dict):
        raise RuntimeError("Mattermost channel creation did not return a JSON object.")
    return response


def find_channel_summary(channel_summaries: list[dict[str, object]], channel_name: str) -> dict[str, object] | None:
    for channel in channel_summaries:
        if str(channel.get("channel_name", "")).strip() == channel_name:
            return channel
    return None


def execute_action(
    plan: dict[str, object],
    *,
    base_url: str,
    token: str,
    me: dict[str, object],
    team_id: str,
    channel_summaries: list[dict[str, object]],
) -> str:
    action = str(plan.get("action", "")).strip()
    message = str(plan.get("message", "")).strip()
    if not message:
        raise RuntimeError("Planner did not provide a message.")
    if action == "reply":
        channel_name = str(plan.get("channel_name", "")).strip()
        root_post_id = str(plan.get("root_post_id", "")).strip()
        channel = find_channel_summary(channel_summaries, channel_name)
        if channel is None or not root_post_id:
            raise RuntimeError("Planner reply action is missing channel_name or root_post_id.")
        channel_id = str(channel.get("channel_id", "")).strip()
        ensure_joined_channel(base_url, token, me, channel_id)
        return f"POSTED {post_message(base_url, token, channel_id, message, root_post_id=root_post_id)}"
    if action == "new_thread":
        channel_name = str(plan.get("channel_name", "")).strip()
        channel = find_channel_summary(channel_summaries, channel_name)
        if channel is None:
            raise RuntimeError("Planner new_thread action is missing channel_name.")
        channel_id = str(channel.get("channel_id", "")).strip()
        ensure_joined_channel(base_url, token, me, channel_id)
        return f"POSTED {post_message(base_url, token, channel_id, message)}"
    if action == "create_channel":
        channel_name = normalize_channel_name(str(plan.get("channel_name", "")).strip())
        display_name = str(plan.get("display_name", "")).strip()
        purpose = str(plan.get("purpose", "")).strip()
        triad_count = sum(1 for item in channel_summaries if str(item.get("channel_name", "")).startswith(CHANNEL_PREFIX))
        if triad_count >= MAX_TRIAD_CHANNELS:
            raise RuntimeError("Planner requested a new channel but the triad channel cap has been reached.")
        created = create_public_channel(base_url, token, team_id, channel_name, display_name, purpose)
        channel_id = str(created.get("id", "")).strip()
        ensure_joined_channel(base_url, token, me, channel_id)
        return f"POSTED {post_message(base_url, token, channel_id, message)}"
    raise RuntimeError(f"Planner returned unsupported action: {action}")


def main(args: argparse.Namespace) -> int:
    instance_id = args.instance
    handle = HANDLES[instance_id]
    runtime = load_control_values()
    mattermost_base_url, mattermost_token = load_mattermost_runtime()
    me = fetch_me(mattermost_base_url, mattermost_token)
    actual_handle = str(me.get("username", "")).strip()
    if actual_handle and actual_handle != handle:
        raise RuntimeError(f"wrong-handle expected={handle} actual={actual_handle}")

    _, team_id = resolve_team(mattermost_base_url, mattermost_token, runtime["team_name"])
    team_channels = list_team_channels(mattermost_base_url, mattermost_token, team_id)
    my_channel_ids = list_my_channels(mattermost_base_url, mattermost_token, team_id)
    channel_summaries = summarize_channels(mattermost_base_url, mattermost_token, team_channels, my_channel_ids, BOT_IDS)

    default_summary = find_channel_summary(channel_summaries, runtime["default_channel"])
    if default_summary is not None:
        posts, order = fetch_channel_posts(mattermost_base_url, mattermost_token, str(default_summary.get("channel_id", "")).strip())
        limited, reason = should_rate_limit(handle, posts, order, BOT_IDS, args.force)
        if limited:
            print(f"IDLE {reason}")
            return 0

    plan = choose_action(instance_id, channel_summaries, args.timeout, runtime["ollama_base_url"], runtime["ollama_model"])
    result = execute_action(
        plan,
        base_url=mattermost_base_url,
        token=mattermost_token,
        me=me,
        team_id=team_id,
        channel_summaries=channel_summaries,
    )
    print(result)
    return 0


BOT_IDS: dict[str, str] = {}


if __name__ == "__main__":
    try:
        parsed_args = parse_args()
        runtime_base_url, runtime_token = load_mattermost_runtime()
        BOT_IDS = resolve_bot_ids(runtime_base_url, runtime_token)
        raise SystemExit(main(parsed_args))
    except Exception as exc:  # pragma: no cover - runtime diagnostic path
        print(f"ERROR {exc}", file=sys.stderr)
        raise
