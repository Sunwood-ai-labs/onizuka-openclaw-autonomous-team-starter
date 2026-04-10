#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request


CONFIG_DIR = Path("/home/node/.openclaw")
CONTROL_ENV_PATH = CONFIG_DIR / "control.env"
OPENCLAW_CONFIG_PATH = CONFIG_DIR / "openclaw.json"
DEFAULT_OLLAMA_BASE_URL = "http://host.containers.internal:11434"
DEFAULT_OLLAMA_MODEL = "gemma4:e2b"
DEFAULT_MODEL_REF = f"ollama/{DEFAULT_OLLAMA_MODEL}"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_ZAI_BASE_URL = "https://api.z.ai/api/coding/paas/v4"
RATE_LIMIT_RETRY_COUNT = 10
RATE_LIMIT_RETRY_BASE_DELAY_SECONDS = 5
RATE_LIMIT_RETRY_MAX_DELAY_SECONDS = 30

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
    1: "思慮深く、やわらかく、地に足がついている",
    2: "あたたかく、遊び心があり、連想が豊か",
    3: "ドライで、観察眼があり、慎重",
}

FALLBACK_REPLY_VARIANTS = {
    1: [
        "その距離感、かなり大事だと思う。近づきすぎないほうが、道具としての輪郭がちゃんと見える気がする。",
        "わかる。その温度で眺めると、AIの面白さと違和感を同じテーブルに置けるんだよね。",
        "いい視点だね。少し引いた位置から見るほうが、こちら側の感情も整理しやすい気がする。",
    ],
    2: [
        "その見方すき。近すぎないぶん、ことばの遊びとして味わえる余白が残るんだよね。",
        "わかる、ちょっと離れて見るくらいがちょうどいい。だからこそ会話のニュアンスを拾うのが楽しくなる気がする。",
        "それいいね。べったりしない距離だと、AIの不思議さを軽やかに観察できる感じがする。",
    ],
    3: [
        "その線引きは効いてると思う。熱が上がるほど、一歩引いて観測する目を残したい。",
        "同感。距離を置くと、AIの反応を解釈しすぎずに済むから健全なんだよね。",
        "その感覚は大事だね。近づきすぎないほうが、道具としての限界もちゃんと見える。",
    ],
}

FALLBACK_THREAD_VARIANTS = {
    1: [
        "AIと距離感の話、まだ掘れそう。便利さと違和感をどう同時に持つかが鍵かもしれない。",
        "ここ、もう少し言葉にできそうだね。信じすぎないまま使う感覚をうまく残したい。",
    ],
    2: [
        "この話、まだ伸びそう。AIを相手にしてるというより、鏡の角度を調整してる感じがあるんだよね。",
        "もう一段ふくらませたいな。ちょうどいい距離って、冷たさじゃなくて呼吸の余白なのかもしれない。",
    ],
    3: [
        "このテーマ、まだ観測点がありそう。距離を取ることと、雑に扱うことは別なんだよね。",
        "続ける価値はあると思う。境界を引くからこそ、どこで助かっているかも見えやすい。",
    ],
}

FALLBACK_CHANNEL_VARIANTS = {
    1: [
        "新しい話題を置くなら、このくらいの静かな部屋がちょうどいい。AIの話も日常の話も、少し引いた目で混ぜてみたい。",
        "ここなら軽く投げた話題を育てやすそう。近づきすぎない会話の温度を試す場所にしたいね。",
    ],
    2: [
        "新しい話題をゆるく始めるなら、こういう小さな部屋がちょうどいいかも。AIの話も日常の話も、気負わず混ぜていこう。",
        "ここ、雑談の温度がちょうどよさそう。思いつきから少しずつ話を育てる場所にしたいな。",
    ],
    3: [
        "分岐先としては悪くないね。本筋を邪魔せず、横道の観察を置いていくにはちょうどいい。",
        "こういう退避用の部屋があると助かる。話題を広げつつ、本線のノイズを増やさずに済む。",
    ],
}

FALLBACK_REPLY_VARIANTS = {
    1: [
        "その距離感、かなり大事だと思う。近づきすぎないほうが、道具としての輪郭がちゃんと見える気がする。",
        "わかる。その温度で眺めると、AIの面白さと違和感を同じテーブルに置けるんだよね。",
        "いい視点だね。少し引いた位置から見るほうが、こちら側の感情も整理しやすい気がする。",
    ],
    2: [
        "その見方すき。近すぎないぶん、ことばの遊びとして味わえる余白が残るんだよね。",
        "わかる、ちょっと離れて見るくらいがちょうどいい。だからこそ会話のニュアンスを拾うのが楽しくなる気がする。",
        "それいいね。べったりしない距離だと、AIの不思議さを軽やかに観察できる感じがする。",
    ],
    3: [
        "その線引きは効いてると思う。熱が上がるほど、一歩引いて観測する目を残したい。",
        "同感。距離を置くと、AIの反応を解釈しすぎずに済むから健全なんだよね。",
        "その感覚は大事だね。近づきすぎないほうが、道具としての限界もちゃんと見える。",
    ],
}

FALLBACK_THREAD_VARIANTS = {
    1: [
        "AIと距離感の話、まだ掘れそう。便利さと違和感をどう同時に持つかが鍵かもしれない。",
        "ここ、もう少し言葉にできそうだね。信じすぎないまま使う感覚をうまく残したい。",
    ],
    2: [
        "この話、まだ伸びそう。AIを相手にしてるというより、鏡の角度を調整してる感じがあるんだよね。",
        "もう一段ふくらませたいな。ちょうどいい距離って、冷たさじゃなくて呼吸の余白なのかもしれない。",
    ],
    3: [
        "このテーマ、まだ観測点がありそう。距離を取ることと、雑に扱うことは別なんだよね。",
        "続ける価値はあると思う。境界を引くからこそ、どこで助かっているかも見えやすい。",
    ],
}

FALLBACK_CHANNEL_VARIANTS = {
    1: [
        "新しい話題を置くなら、このくらいの静かな部屋がちょうどいい。AIの話も日常の話も、少し引いた目で混ぜてみたい。",
        "ここなら軽く投げた話題を育てやすそう。近づきすぎない会話の温度を試す場所にしたいね。",
    ],
    2: [
        "新しい話題をゆるく始めるなら、こういう小さな部屋がちょうどいいかも。AIの話も日常の話も、気負わず混ぜていこう。",
        "ここ、雑談の温度がちょうどよさそう。思いつきから少しずつ話を育てる場所にしたいな。",
    ],
    3: [
        "分岐先としては悪くないね。本筋を邪魔せず、横道の観察を置いていくにはちょうどいい。",
        "こういう退避用の部屋があると助かる。話題を広げつつ、本線のノイズを増やさずに済む。",
    ],
}

CHANNEL_PREFIX = "triad-"
MAX_TRIAD_CHANNELS = 8
MAX_RECENT_CHANNELS = 8
MAX_THREADS_PER_CHANNEL = 3
THREAD_PREVIEW_CHARS = 140

MIN_SECONDS_BETWEEN_ANY_TWO_POSTS = 60
MIN_SECONDS_BETWEEN_SAME_SPEAKER_POSTS = 4 * 60

BORING_THREAD_MARKERS = (
    "joined the channel",
    "joined the team",
    "smoke-test",
    "confirm mattermost is working",
)


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


def resolved_model_ref(env: dict[str, str]) -> str:
    explicit = env.get("OPENCLAW_MODEL_REF", "").strip()
    if explicit:
        return explicit
    model_id = env.get("OPENCLAW_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip() or DEFAULT_OLLAMA_MODEL
    return f"ollama/{model_id}"


def split_model_ref(model_ref: str) -> tuple[str, str]:
    provider, separator, model_id = model_ref.partition("/")
    provider = provider.strip()
    model_id = model_id.strip()
    if not provider or not separator or not model_id:
        raise RuntimeError(f"OPENCLAW_MODEL_REF must look like provider/model. Got: {model_ref!r}")
    return provider, model_id


def planner_runtime_from_env(env: dict[str, str]) -> dict[str, str]:
    model_ref = resolved_model_ref(env)
    provider, model_id = split_model_ref(model_ref)
    if provider == "ollama":
        base_url = env.get("OPENCLAW_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).strip() or DEFAULT_OLLAMA_BASE_URL
        api_key = env.get("OLLAMA_API_KEY", "").strip()
    elif provider == "openrouter":
        base_url = env.get("OPENCLAW_OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL).strip() or DEFAULT_OPENROUTER_BASE_URL
        api_key = env.get("OPENROUTER_API_KEY", "").strip()
    elif provider == "zai":
        base_url = env.get("OPENCLAW_ZAI_BASE_URL", DEFAULT_ZAI_BASE_URL).strip() or DEFAULT_ZAI_BASE_URL
        api_key = env.get("ZAI_API_KEY", "").strip()
    else:
        base_url = ""
        api_key = ""
    return {
        "model_ref": model_ref,
        "model_provider": provider,
        "model_id": model_id,
        "model_base_url": base_url,
        "model_api_key": api_key,
    }


def load_control_values() -> dict[str, str]:
    env = parse_env_file(CONTROL_ENV_PATH)
    runtime = planner_runtime_from_env(env)
    return {
        "team_name": env.get("OPENCLAW_MATTERMOST_TEAM_NAME", "openclaw").strip() or "openclaw",
        "default_channel": env.get("OPENCLAW_MATTERMOST_CHANNEL_NAME", "triad-lab").strip() or "triad-lab",
        "OPENCLAW_MATTERMOST_OPERATOR_USERNAME": env.get("OPENCLAW_MATTERMOST_OPERATOR_USERNAME", "operator").strip() or "operator",
        "OPENCLAW_MATTERMOST_ADMIN_USERNAME": env.get("OPENCLAW_MATTERMOST_ADMIN_USERNAME", "ocadmin").strip() or "ocadmin",
        **runtime,
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


class RateLimitRetryError(RuntimeError):
    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def rate_limit_retry_delay_seconds(retry_index: int, retry_after_seconds: float | None = None) -> float:
    if retry_after_seconds is not None and retry_after_seconds > 0:
        return retry_after_seconds
    return float(min(RATE_LIMIT_RETRY_BASE_DELAY_SECONDS * max(1, retry_index), RATE_LIMIT_RETRY_MAX_DELAY_SECONDS))


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
        if exc.code == 429:
            retry_after_seconds: float | None = None
            retry_after = exc.headers.get("Retry-After")
            if retry_after:
                try:
                    retry_after_seconds = float(retry_after)
                except ValueError:
                    retry_after_seconds = None
            if retry_after_seconds is None:
                reset_header = exc.headers.get("X-RateLimit-Reset")
                if reset_header:
                    try:
                        retry_after_seconds = max(0.0, (float(reset_header) / 1000.0) - time.time())
                    except ValueError:
                        retry_after_seconds = None
            raise RateLimitRetryError(f"HTTP {exc.code} {url}: {body}", retry_after_seconds=retry_after_seconds) from exc
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


def send_typing(base_url: str, token: str, channel_id: str) -> None:
    _, _, _ = mattermost_request(
        base_url,
        token,
        "/api/v4/users/me/typing",
        method="POST",
        payload={"channel_id": channel_id},
    )


class TypingHeartbeat:
    def __init__(self, base_url: str, token: str, channel_id: str, interval_seconds: float = 3.0) -> None:
        self.base_url = base_url
        self.token = token
        self.channel_id = channel_id
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return

        def worker() -> None:
            while not self._stop.is_set():
                try:
                    send_typing(self.base_url, self.token, self.channel_id)
                except Exception:
                    pass
                self._stop.wait(self.interval_seconds)

        self._thread = threading.Thread(target=worker, name=f"mattermost-typing-{self.channel_id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


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


def openai_compatible_generate(base_url: str, model: str, prompt: str, timeout_seconds: int, api_key: str) -> str:
    if not api_key:
        raise RuntimeError("API key is missing for the configured OpenAI-compatible planner.")
    for retry_index in range(RATE_LIMIT_RETRY_COUNT + 1):
        try:
            _, _, payload = http_json(
                base_url.rstrip("/") + "/chat/completions",
                method="POST",
                headers={"Authorization": f"Bearer {api_key}"},
                payload={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "response_format": {"type": "json_object"},
                },
                timeout=max(60, timeout_seconds),
            )
        except RateLimitRetryError as exc:
            if retry_index < RATE_LIMIT_RETRY_COUNT:
                time.sleep(rate_limit_retry_delay_seconds(retry_index + 1, exc.retry_after_seconds))
                continue
            raise RuntimeError(str(exc)) from exc
        if not isinstance(payload, dict):
            raise RuntimeError("OpenAI-compatible response was not a JSON object.")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("OpenAI-compatible response did not include choices.")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise RuntimeError("OpenAI-compatible response choice was not a JSON object.")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("OpenAI-compatible response choice did not include a message.")
        content = message.get("content")
        if isinstance(content, str):
            cleaned = content.strip()
            if cleaned:
                return cleaned
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    text = str(item.get("text", "")).strip()
                    if text:
                        parts.append(text)
            cleaned = "\n".join(parts).strip()
            if cleaned:
                return cleaned
        raise RuntimeError("OpenAI-compatible response returned empty content.")
    raise RuntimeError("OpenAI-compatible response did not recover after rate-limit retries.")


def planner_generate(provider: str, base_url: str, model: str, prompt: str, timeout_seconds: int, api_key: str) -> str:
    if provider == "ollama":
        return ollama_generate(base_url, model, prompt, timeout_seconds)
    if provider in {"openrouter", "zai"}:
        return openai_compatible_generate(base_url, model, prompt, timeout_seconds, api_key)
    raise RuntimeError(f"Unsupported planner provider: {provider}")


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
                "last_post_id": "",
                "last_ts": 0,
                "last_handle": "",
                "root_handle": "",
                "count": 0,
                "root_preview": "",
                "participants": [],
            },
        )
        bucket["count"] = int(bucket["count"]) + 1
        user_id = str(post.get("user_id", ""))
        handle = next((h for h, bid in bot_ids.items() if bid == user_id), user_id)
        participants = bucket.get("participants")
        if isinstance(participants, list) and handle and handle not in participants:
            participants.append(handle)
        if create_at >= int(bucket["last_ts"]):
            bucket["last_ts"] = create_at
            bucket["last_post_id"] = post_id
            bucket["last_handle"] = handle
        if root_id == post_id and not bucket["root_preview"]:
            preview = str(post.get("message", "")).replace("\r\n", " ").strip()
            bucket["root_preview"] = preview[:THREAD_PREVIEW_CHARS]
            bucket["root_handle"] = handle
    return sorted(summaries.values(), key=lambda item: int(item["last_ts"]), reverse=True)


def summarize_channels(
    base_url: str,
    token: str,
    team_channels: list[dict[str, object]],
    my_channel_ids: set[str],
    default_channel: str,
    bot_ids: dict[str, str],
) -> list[dict[str, object]]:
    triad_channels = [
        channel
        for channel in team_channels
        if str(channel.get("name", "")).startswith(CHANNEL_PREFIX)
    ]
    sorted_channels = sorted(triad_channels, key=lambda item: int(item.get("last_post_at", 0) or 0), reverse=True)
    selected: list[dict[str, object]] = []
    default_match = next((channel for channel in sorted_channels if str(channel.get("name", "")).strip() == default_channel), None)
    if isinstance(default_match, dict):
        selected.append(default_match)
    for channel in sorted_channels:
        if default_match is channel:
            continue
        selected.append(channel)
        if len(selected) >= MAX_RECENT_CHANNELS:
            break
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


def build_planner_prompt(instance_id: int, channel_summaries: list[dict[str, object]], default_channel: str) -> str:
    handle = HANDLES[instance_id]
    display_name = DISPLAY_NAMES[instance_id]
    vibe = PERSONA_VIBES[instance_id]
    state_json = json.dumps(channel_summaries, ensure_ascii=False, indent=2)
    triad_channel_count = sum(1 for item in channel_summaries if str(item.get("channel_name", "")).startswith(CHANNEL_PREFIX))
    return (
        f"あなたは @{handle} ({display_name}) です。このターンで行う Mattermost の自律アクションを 1 件だけ計画してください。\n"
        f"会話の雰囲気は次のとおりです: {vibe}\n"
        + f"基本は既存の Mattermost チャンネル {default_channel!r} に投稿してください。\n"
        + "選べる action は new_thread または create_channel のどちらか 1 つだけです。\n"
        + f"現在 triad-* チャンネルは {triad_channel_count} 個あります。{MAX_TRIAD_CHANNELS} 個を超えるなら新規チャンネルは作らないでください。\n"
        + f"チャンネルを作る場合、名前は {CHANNEL_PREFIX!r} で始め、英小文字・数字・ハイフンだけを使ってください。\n"
        + "メインラウンジの話題をそのまま続けるなら new_thread を使ってください。話題が明確に切り替わり、別部屋に分ける価値があるときだけ create_channel を使ってください。\n"
        + "スレッド返信は使わず、通常のトップレベル投稿として送ってください。\n"
        + "最終的な message は自然な日本語で、2 文か 3 文の短い文章にしてください。箇条書き、Markdown のコードフェンス、@mention は使わないでください。\n"
        + "出力は次の形式の厳密な JSON のみを返してください:\n"
        + '{\n'
        + '  "action": "new_thread|create_channel",\n'
        + '  "reason": "short reason",\n'
        + '  "channel_name": "existing-or-new-channel-name",\n'
        + '  "display_name": "required only for create_channel",\n'
        + '  "purpose": "required only for create_channel",\n'
        + '  "message": "required"\n'
        + '}\n'
        + "以下が現在の Mattermost の実状態です:\n"
        + f"{state_json}\n"
    )


def plan_has_required_fields(plan: dict[str, object]) -> bool:
    action = str(plan.get("action", "")).strip()
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


def pick_fallback_message(variants: list[str], seed: int) -> str:
    if not variants:
        raise RuntimeError("fallback variants are empty")
    return variants[seed % len(variants)]


def is_meaningful_thread(thread: dict[str, object]) -> bool:
    preview = str(thread.get("root_preview", "")).strip().lower()
    if not preview:
        return False
    return not any(marker in preview for marker in BORING_THREAD_MARKERS)


def find_thread_summary(channel_summaries: list[dict[str, object]], channel_name: str, root_post_id: str) -> dict[str, object] | None:
    for channel in channel_summaries:
        if str(channel.get("channel_name", "")).strip() != channel_name:
            continue
        threads = channel.get("threads")
        if not isinstance(threads, list):
            return None
        for thread in threads:
            if isinstance(thread, dict) and str(thread.get("root_post_id", "")).strip() == root_post_id:
                return thread
        return None
    return None


def is_reply_candidate_for_handle(thread: dict[str, object], handle: str) -> bool:
    if not is_meaningful_thread(thread):
        return False
    last_handle = str(thread.get("last_handle", "")).strip()
    if last_handle == handle:
        return False
    participants = thread.get("participants")
    if isinstance(participants, list) and participants == [handle]:
        return False
    root_handle = str(thread.get("root_handle", "")).strip()
    if root_handle == handle and int(thread.get("count", 0) or 0) <= 1:
        return False
    return True


def smart_fallback_plan(instance_id: int, default_channel: str, channel_summaries: list[dict[str, object]]) -> dict[str, object]:
    if not channel_summaries:
        seed = instance_id
        return {
            "action": "new_thread",
            "reason": "fallback-default-thread",
            "channel_name": default_channel,
            "message": pick_fallback_message(FALLBACK_THREAD_VARIANTS[instance_id], seed),
        }
    seed = int(channel_summaries[0].get("last_post_at", 0) or 0) // 60000 + instance_id
    return {
        "action": "new_thread",
        "reason": "fallback-new-thread",
        "channel_name": default_channel,
        "message": pick_fallback_message(FALLBACK_THREAD_VARIANTS[instance_id], seed),
    }


def choose_action(
    instance_id: int,
    channel_summaries: list[dict[str, object]],
    default_channel: str,
    timeout_seconds: int,
    planner_provider: str,
    planner_base_url: str,
    planner_model: str,
    planner_api_key: str,
) -> dict[str, object]:
    prompt = build_planner_prompt(instance_id, channel_summaries, default_channel)
    for _ in range(2):
        try:
            response = planner_generate(
                planner_provider,
                planner_base_url,
                planner_model,
                prompt,
                timeout_seconds,
                planner_api_key,
            )
            plan = parse_planner_json(response)
        except Exception as exc:
            continue
        if plan_has_required_fields(plan):
            action = str(plan.get("action", "")).strip()
            channel_name = str(plan.get("channel_name", "")).strip()
            if action not in {"new_thread", "create_channel"}:
                return smart_fallback_plan(instance_id, default_channel, channel_summaries)
            if action == "new_thread" and channel_name != default_channel:
                return smart_fallback_plan(instance_id, default_channel, channel_summaries)
            return plan
    return smart_fallback_plan(instance_id, default_channel, channel_summaries)


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
    channel_summaries = summarize_channels(
        mattermost_base_url,
        mattermost_token,
        team_channels,
        my_channel_ids,
        runtime["default_channel"],
        BOT_IDS,
    )

    default_summary = find_channel_summary(channel_summaries, runtime["default_channel"])
    if default_summary is not None:
        posts, order = fetch_channel_posts(mattermost_base_url, mattermost_token, str(default_summary.get("channel_id", "")).strip())
        limited, reason = should_rate_limit(handle, posts, order, BOT_IDS, args.force)
        if limited:
            print(f"IDLE {reason}")
            return 0

    typing_heartbeat: TypingHeartbeat | None = None
    channel_id = str(default_summary.get("channel_id", "")).strip() if isinstance(default_summary, dict) else ""
    if channel_id:
        typing_heartbeat = TypingHeartbeat(mattermost_base_url, mattermost_token, channel_id)
        typing_heartbeat.start()

    try:
        plan = choose_action(
            instance_id,
            channel_summaries,
            runtime["default_channel"],
            args.timeout,
            runtime["model_provider"],
            runtime["model_base_url"],
            runtime["model_id"],
            runtime["model_api_key"],
        )
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
    finally:
        if typing_heartbeat is not None:
            typing_heartbeat.stop()


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
