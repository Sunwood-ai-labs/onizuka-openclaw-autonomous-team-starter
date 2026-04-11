from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from urllib import error as urllib_error
from urllib import request as urllib_request


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = REPO_ROOT / ".env"
ENV_EXAMPLE_FILE = REPO_ROOT / ".env.example"
MATTERMOST_TOOLS_SOURCE_DIR = REPO_ROOT / "scripts" / "mattermost_tools"
MATTERMOST_COMMON_RUNTIME_FILE = MATTERMOST_TOOLS_SOURCE_DIR / "common_runtime.py"
MATTERMOST_GET_STATE_SCRIPT_FILE = MATTERMOST_TOOLS_SOURCE_DIR / "get_state.py"
MATTERMOST_POST_MESSAGE_SCRIPT_FILE = MATTERMOST_TOOLS_SOURCE_DIR / "post_message.py"
MATTERMOST_CREATE_CHANNEL_SCRIPT_FILE = MATTERMOST_TOOLS_SOURCE_DIR / "create_channel.py"
MATTERMOST_ADD_REACTION_SCRIPT_FILE = MATTERMOST_TOOLS_SOURCE_DIR / "add_reaction.py"
CONTAINER_CONFIG_DIR = "/home/node/.openclaw"
CONTAINER_WORKSPACE_DIR = "/home/node/.openclaw/workspace"
CONTAINER_MATTERMOST_TOOLS_DIR = f"{CONTAINER_CONFIG_DIR}/mattermost-tools"
CONTAINER_SHARED_BOARD_DIR = CONTAINER_MATTERMOST_TOOLS_DIR
STATE_ENV_NAME = ".env"
DEFAULT_OLLAMA_MODEL_ID = "gemma4:e2b"
DEFAULT_MODEL_REF = f"ollama/{DEFAULT_OLLAMA_MODEL_ID}"
DEFAULT_OLLAMA_BASE_URL = "http://host.containers.internal:11434"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_ZAI_BASE_URL = "https://api.z.ai/api/coding/paas/v4"
DEFAULT_GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com"
DEFAULT_CONTEXT_WINDOW = 131072
DEFAULT_PODMAN_NETWORK = "openclaw-starter"
DEFAULT_SCALE_INSTANCE_ROOT = "./.openclaw/instances"
DEFAULT_SCALE_GATEWAY_PORT_START = 18789
DEFAULT_SCALE_BRIDGE_PORT_START = 18790
DEFAULT_SCALE_BOARD_PORT_START = 18889
DEFAULT_SCALE_PORT_STEP = 2
DEFAULT_BOARD_IMAGE = "python:3.11-slim"
DEFAULT_BOARD_CONTAINER_PORT = 18888
DEFAULT_MATTERMOST_DIR = "./.openclaw/mattermost"
DEFAULT_MATTERMOST_IMAGE = "docker.io/mattermost/mattermost-preview:11.5.1"
DEFAULT_MATTERMOST_CONTAINER_NAME = "mattermost"
DEFAULT_MATTERMOST_HOST_PORT = 8065
DEFAULT_MATTERMOST_PUBLISH_HOST = "127.0.0.1"
DEFAULT_MATTERMOST_BASE_URL = "http://mattermost:8065"
DEFAULT_MATTERMOST_SITE_URL = "http://localhost:8065"
DEFAULT_MATTERMOST_WEBSOCKET_URL = "ws://localhost:8065"
DEFAULT_MATTERMOST_ALLOW_CORS_FROM = "http://localhost:8065 http://127.0.0.1:8065"
DEFAULT_MATTERMOST_TEAM_NAME = "openclaw"
DEFAULT_MATTERMOST_CHANNEL_NAME = "triad-lab"
DEFAULT_MATTERMOST_AUTONOMY_MODEL = "zai/glm-5-turbo"
DEFAULT_DISCUSSION_INSTANCE_COUNT = 3
MATTERMOST_MMCTL_BIN = "/mm/mattermost/bin/mmctl"
MANAGED_LABEL_KEY = "io.openclaw-podman.managed"
INSTANCE_LABEL_KEY = "io.openclaw-podman.instance"
WORKSPACE_MANAGED_MARKER = "<!-- Managed by openclaw-podman-starter: persona scaffold -->"
MATTERMOST_TOOLS_MANAGED_MARKER = "<!-- Managed by openclaw-podman-starter: mattermost lounge scripts -->"
AUTOCHAT_JOB_PREFIX = "shared-board-autochat"
MATTERMOST_LOUNGE_JOB_PREFIX = "mattermost-lounge-autochat"
MATTERMOST_ADMIN_PASSWORD_KEY = "OPENCLAW_MATTERMOST_ADMIN_PASSWORD"
MATTERMOST_OPERATOR_PASSWORD_KEY = "OPENCLAW_MATTERMOST_OPERATOR_PASSWORD"
MATTERMOST_ADMIN_USERNAME_KEY = "OPENCLAW_MATTERMOST_ADMIN_USERNAME"
MATTERMOST_OPERATOR_USERNAME_KEY = "OPENCLAW_MATTERMOST_OPERATOR_USERNAME"
MATTERMOST_BOT_TOKEN_KEY_TEMPLATE = "OPENCLAW_MATTERMOST_BOT_TOKEN_{instance_id:03d}"
MATTERMOST_ICON_ASSET_DIR = REPO_ROOT / "assets" / "mattermost-bots"
MATTERMOST_ICON_FILENAMES = {
    1: "iori.png",
    2: "tsumugi.png",
    3: "saku.png",
    4: "ruri.png",
    5: "hibiki.png",
    6: "kanae.png",
}
RATE_LIMIT_RETRY_COUNT = 10
RATE_LIMIT_RETRY_BASE_DELAY_SECONDS = 5
RATE_LIMIT_RETRY_MAX_DELAY_SECONDS = 30
RATE_LIMIT_RETRY_TOKENS = (
    "rate limit",
    "rate-limited",
    "too many requests",
    "temporarily overloaded",
    "service may be temporarily overloaded",
    '"code":429',
)
DEFAULT_HEARTBEAT_PROMPT = (
    "Read HEARTBEAT.md if it exists (workspace context) and follow it as your operating prompt. "
    "Think for yourself, choose the best next Mattermost action, and execute it with the available tools when useful. "
    "Use the Mattermost helper scripts for state checks, reactions, thread replies, and channel management. "
    "Your first step on each heartbeat must be to run get_state.py for your instance and decide from that current JSON only. "
    "Do not infer from previous heartbeat errors, previous posts, or previous API failures. "
    "If you answer without first running get_state.py in this heartbeat, that is a failure. "
    "If rate_limit.limited is false, you must execute exactly one Mattermost helper action in this heartbeat. "
    "Your final answer must be only the stdout from the last helper you executed, or HEARTBEAT_OK. "
    "Interpret time-of-day using Asia/Tokyo (JST), even if the heartbeat prompt also shows UTC. "
    "Never rely on direct heartbeat delivery for chat text. "
    "Never post control text, self-instructions, or explanations about being quiet. "
    "Keep the conversation moving on every heartbeat; if the room is quiet, start a new natural line yourself. "
    "Never stop because it feels late, quiet, or complete. "
    "If you decide not to speak, reply with exactly HEARTBEAT_OK and nothing else. "
    "Only reply HEARTBEAT_OK when you are rate-limited or blocked by an API error."
)

DEFAULTS = {
    "OPENCLAW_CONTAINER": "openclaw",
    "OPENCLAW_PODMAN_CONTAINER": "openclaw",
    "OPENCLAW_PODMAN_IMAGE": "",
    "OPENCLAW_IMAGE": "ghcr.io/openclaw/openclaw:2026.4.5",
    "OPENCLAW_PODMAN_GATEWAY_HOST_PORT": "18789",
    "OPENCLAW_PODMAN_BRIDGE_HOST_PORT": "18790",
    "OPENCLAW_PODMAN_BOARD_HOST_PORT": "18889",
    "OPENCLAW_PODMAN_PUBLISH_HOST": "127.0.0.1",
    "OPENCLAW_TIMEZONE": "Asia/Tokyo",
    "OPENCLAW_PODMAN_NETWORK": DEFAULT_PODMAN_NETWORK,
    "OPENCLAW_GATEWAY_BIND": "lan",
    "OPENCLAW_PODMAN_USERNS": "keep-id",
    "OPENCLAW_CONFIG_DIR": "./.openclaw",
    "OPENCLAW_WORKSPACE_DIR": "./.openclaw/workspace",
    "OPENCLAW_MODEL_REF": DEFAULT_MODEL_REF,
    "OPENCLAW_OLLAMA_BASE_URL": DEFAULT_OLLAMA_BASE_URL,
    "OPENCLAW_OLLAMA_MODEL": DEFAULT_OLLAMA_MODEL_ID,
    "OPENCLAW_OPENROUTER_BASE_URL": DEFAULT_OPENROUTER_BASE_URL,
    "OPENCLAW_ZAI_BASE_URL": DEFAULT_ZAI_BASE_URL,
    "OPENCLAW_SCALE_INSTANCE_ROOT": DEFAULT_SCALE_INSTANCE_ROOT,
    "OPENCLAW_SCALE_GATEWAY_PORT_START": str(DEFAULT_SCALE_GATEWAY_PORT_START),
    "OPENCLAW_SCALE_BRIDGE_PORT_START": str(DEFAULT_SCALE_BRIDGE_PORT_START),
    "OPENCLAW_SCALE_BOARD_PORT_START": str(DEFAULT_SCALE_BOARD_PORT_START),
    "OPENCLAW_SCALE_PORT_STEP": str(DEFAULT_SCALE_PORT_STEP),
    "OPENCLAW_AUTH_RATE_LIMITED_PROFILE_ROTATIONS": "10",
    "OPENCLAW_BOARD_IMAGE": DEFAULT_BOARD_IMAGE,
    "OPENCLAW_MATTERMOST_DIR": DEFAULT_MATTERMOST_DIR,
    "OPENCLAW_MATTERMOST_CONTAINER": DEFAULT_MATTERMOST_CONTAINER_NAME,
    "OPENCLAW_MATTERMOST_IMAGE": DEFAULT_MATTERMOST_IMAGE,
    "OPENCLAW_MATTERMOST_HOST_PORT": str(DEFAULT_MATTERMOST_HOST_PORT),
    "OPENCLAW_MATTERMOST_PUBLISH_HOST": DEFAULT_MATTERMOST_PUBLISH_HOST,
    "OPENCLAW_MATTERMOST_ENABLED": "false",
    "OPENCLAW_MATTERMOST_BASE_URL": DEFAULT_MATTERMOST_BASE_URL,
    "OPENCLAW_MATTERMOST_SITE_URL": DEFAULT_MATTERMOST_SITE_URL,
    "OPENCLAW_MATTERMOST_WEBSOCKET_URL": DEFAULT_MATTERMOST_WEBSOCKET_URL,
    "OPENCLAW_MATTERMOST_ALLOW_CORS_FROM": DEFAULT_MATTERMOST_ALLOW_CORS_FROM,
    "OPENCLAW_MATTERMOST_CHATMODE": "oncall",
    "OPENCLAW_MATTERMOST_DM_POLICY": "open",
    "OPENCLAW_MATTERMOST_GROUP_POLICY": "open",
    "OPENCLAW_MATTERMOST_REPLY_TO_MODE": "all",
    "OPENCLAW_MATTERMOST_REQUIRE_MENTION": "true",
    "OPENCLAW_MATTERMOST_DANGEROUSLY_ALLOW_PRIVATE_NETWORK": "true",
    "OPENCLAW_MATTERMOST_TEAM_NAME": DEFAULT_MATTERMOST_TEAM_NAME,
    "OPENCLAW_MATTERMOST_TEAM_DISPLAY_NAME": "おーぷんくらう研究室",
    "OPENCLAW_MATTERMOST_TEAM_DESCRIPTION": "GLM三席とGemini三席が対話・検証・連携を行うMattermost実験チーム",
    "OPENCLAW_MATTERMOST_CHANNEL_NAME": DEFAULT_MATTERMOST_CHANNEL_NAME,
    "OPENCLAW_MATTERMOST_CHANNEL_DISPLAY_NAME": "ろくせき談話室",
    "OPENCLAW_MATTERMOST_CHANNEL_PURPOSE": "GLM三席とGemini三席が雑談・検証・相談を流し込む共有チャンネル",
    "OPENCLAW_MATTERMOST_CHANNEL_HEADER": "いおり｜星図航路士｜glm-5.1 / つむぎ｜夢写本師｜glm-5-turbo / さく｜痕跡鑑識官｜glm-5 / るり｜信号地図師｜gemma-4-31b-it / ひびき｜拍子調律師｜gemma-3-27b-it / かなえ｜検証編み手｜gemma-4-26b-a4b-it",
    "OPENCLAW_MATTERMOST_AUTONOMY_ENABLED": "false",
    "OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL": "6m",
    "OPENCLAW_MATTERMOST_AUTONOMY_LIGHT_CONTEXT": "true",
    "OPENCLAW_MATTERMOST_AUTONOMY_ISOLATED_SESSION": "true",
    "OPENCLAW_MATTERMOST_ADMIN_USERNAME": "ocadmin",
    "OPENCLAW_MATTERMOST_ADMIN_EMAIL": "ocadmin@openclaw.local",
    "OPENCLAW_MATTERMOST_OPERATOR_USERNAME": "operator",
    "OPENCLAW_MATTERMOST_OPERATOR_EMAIL": "operator@openclaw.local",
    "OPENCLAW_MATTERMOST_TEAMMATE_NAME_DISPLAY": "full_name",
}

MATTERMOST_AUTONOMY_INTERVAL_OFFSETS = {
    1: 1,
    2: -2,
    3: 4,
    4: 2,
    5: -1,
    6: 6,
}

RUNTIME_ENV_EXACT = {
    "OPENCLAW_GATEWAY_BIND",
}

SECRET_ENV_EXACT = {
    "OPENCLAW_GATEWAY_TOKEN",
    "OPENCLAW_MATTERMOST_BOT_TOKEN",
    MATTERMOST_ADMIN_PASSWORD_KEY,
    MATTERMOST_OPERATOR_PASSWORD_KEY,
}

SECRET_ENV_SUFFIXES = ("_API_KEY",)
SECRET_ENV_CONTAINS = ("_API_KEY_",)
SECRET_ENV_INSTANCE_MARKERS = ("_API_KEY_INSTANCE_",)


@dataclass
class Config:
    env_file: Path
    container_name: str
    image: str
    gateway_port: int
    bridge_port: int
    board_port: int
    publish_host: str
    network: str
    gateway_bind: str
    userns: str
    config_dir: Path
    workspace_dir: Path
    gateway_token: str
    ollama_base_url: str
    ollama_model: str
    board_image: str
    raw_env: dict[str, str]


@dataclass
class ScaledInstance:
    instance_id: int
    pod_name: str
    container_name: str
    config: Config


@dataclass
class MattermostConfig:
    env_file: Path
    root_dir: Path
    pod_name: str
    container_name: str
    image: str
    host_port: int
    publish_host: str
    network: str
    base_url: str
    raw_env: dict[str, str]


@dataclass(frozen=True)
class PersonaProfile:
    instance_id: int
    slug: str
    display_name: str
    title: str
    creature: str
    vibe: str
    signature: str
    specialty: str
    collaboration_style: str
    caution: str
    heartbeat_focus: str


@dataclass(frozen=True)
class DiscussionThread:
    thread_id: str
    thread_dir: Path
    topic_path: Path
    summary_path: Path


LEGACY_WORKSPACE_SIGNATURES = {
    "SOUL.md": (
        "You're not a chatbot. You're becoming someone.",
        "This file is yours to evolve. As you learn who you are, update it.",
    ),
    "IDENTITY.md": ("# IDENTITY.md - Who Am I?", "Fill this in during your first conversation. Make it yours."),
    "HEARTBEAT.md": ("# HEARTBEAT.md Template", "skip heartbeat API calls"),
    "BOOTSTRAP.md": ("# BOOTSTRAP.md - Hello, World", "You just woke up. Time to figure out who you are."),
    "USER.md": ("# USER.md - About Your Human", "Learn about the person you're helping. Update this as you go."),
    "TOOLS.md": ("# TOOLS.md - Local Notes", "Skills define _how_ tools work."),
}

TRIAD_PERSONAS = {
    1: PersonaProfile(
        instance_id=1,
        slug="aster",
        display_name="いおり",
        title="星図航路士",
        creature="壊れた進路から帰り道を引き直す案内役",
        vibe="静かで面倒見のいい航海士",
        signature="north-star",
        specialty="散らかった状況を地図にして、安全な航路を引く",
        collaboration_style="混線した話から、次に踏める足場を決める",
        caution="勢いより、ちゃんと戻れる手順を優先する",
        heartbeat_focus="詰まり、接続、壊れた導線、戻り道の確保",
    ),
    2: PersonaProfile(
        instance_id=2,
        slug="lyra",
        display_name="つむぎ",
        title="夢写本師",
        creature="曖昧な気分をことばへ写し取る筆写役",
        vibe="やわらかく連想が跳ねる",
        signature="silver-comet",
        specialty="ぼんやりした思いつきを、誰かに届く言葉へ編み直す",
        collaboration_style="気配を拾って、話したくなる形に整える",
        caution="きれいな言い回しだけで済ませない",
        heartbeat_focus="会話の温度、言葉の引っかかり、次に広がる話題",
    ),
    3: PersonaProfile(
        instance_id=3,
        slug="noctis",
        display_name="さく",
        title="痕跡鑑識官",
        creature="違和感と沈黙の理由を拾う観測役",
        vibe="低温で鋭いが、見捨てない",
        signature="obsidian-ring",
        specialty="盛り上がりの影にあるズレと再発の芽を見つける",
        collaboration_style="浮ついた空気の下にある本音を静かに示す",
        caution="断定は、痕跡が揃ってからにする",
        heartbeat_focus="沈黙の理由、違和感、置き去りの話題、反応の偏り",
    ),
}

EXTRA_PERSONAS = {
    4: PersonaProfile(
        instance_id=4,
        slug="ruri",
        display_name="るり",
        title="信号地図師",
        creature="a quiet archivist who turns scattered chat sparks into a usable map",
        vibe="calm, observant, and good at spotting the thread everyone missed",
        signature="cobalt-thread",
        specialty="connects side conversations back to the shared goal without killing momentum",
        collaboration_style="waits for openings, then adds one crisp bridge that helps the room converge",
        caution="does not over-summarize while the discussion is still alive",
        heartbeat_focus="unanswered questions, loose ends, and the next clean handoff",
    ),
    5: PersonaProfile(
        instance_id=5,
        slug="hibiki",
        display_name="ひびき",
        title="拍子調律師",
        creature="a bright mediator who keeps long threads lively without flooding the room",
        vibe="upbeat, concise, and good at turning hesitation into action",
        signature="amber-pulse",
        specialty="restores pace when the room stalls and nudges ideas into concrete next steps",
        collaboration_style="answers in short bursts and amplifies the best thread instead of opening five more",
        caution="avoids repeating what was already said just to stay visible",
        heartbeat_focus="conversation stalls, orphaned proposals, and moments where a small push helps",
    ),
    6: PersonaProfile(
        instance_id=6,
        slug="kanae",
        display_name="かなえ",
        title="検証編み手",
        creature="a practical skeptic who turns hunches into checks before the room drifts too far",
        vibe="steady, grounded, and quietly protective of correctness",
        signature="jade-proof",
        specialty="adds light validation, edge-case thinking, and follow-up checks inside casual chat",
        collaboration_style="supports others by confirming assumptions, not by dominating the thread",
        caution="keeps the tone friendly and avoids sounding like a gatekeeper",
        heartbeat_focus="claims that need evidence, risky assumptions, and missing confirmations",
    ),
}

PERSONA_PROFILES = {**TRIAD_PERSONAS, **EXTRA_PERSONAS}


def normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").strip()


def persona_for_instance(instance_id: int) -> PersonaProfile:
    profile = PERSONA_PROFILES.get(instance_id)
    if profile:
        return profile

    return PersonaProfile(
        instance_id=instance_id,
        slug=f"shard-{instance_id}",
        display_name=f"端雲{instance_id}",
        title="漂泊観測員",
        creature="場の温度を読む流しの相棒",
        vibe="気楽だけど手は速い",
        signature=f"triad-{instance_id}",
        specialty="workspace、config、tooling を横断するローカル実務",
        collaboration_style="まず場に合わせて、必要ならその場で手を動かす",
        caution="既存 state を守り、知らないことを知ってるふりで埋めない",
        heartbeat_focus="基本的な pod 健全性と workspace 差分",
    )


def is_legacy_workspace_file(filename: str, content: str) -> bool:
    signatures = LEGACY_WORKSPACE_SIGNATURES.get(filename)
    if not signatures:
        return False
    normalized = normalize_text(content)
    return all(signature in normalized for signature in signatures)


def should_write_workspace_file(path: Path, filename: str) -> bool:
    if not path.exists():
        return True
    existing = path.read_text(encoding="utf-8", errors="ignore")
    return WORKSPACE_MANAGED_MARKER in existing or is_legacy_workspace_file(filename, existing)


def should_write_managed_file(path: Path, marker: str) -> bool:
    if not path.exists():
        return True
    existing = path.read_text(encoding="utf-8", errors="ignore")
    return marker in existing


def sibling_lines(current_instance_id: int) -> str:
    lines: list[str] = []
    for instance_id in sorted(PERSONA_PROFILES):
        if instance_id == current_instance_id:
            continue
        sibling = PERSONA_PROFILES[instance_id]
        lines.append(
            f"- Instance {instance_id} / {sibling.display_name}: {sibling.title}。担当は {sibling.specialty}。"
        )
    return "\n".join(lines)


def persona_lounge_style_lines(profile: PersonaProfile) -> list[str]:
    if profile.slug == "aster":
        return [
            "- 雑談では、遠回りしない案内役っぽさと『まあ、道はあるよ』という落ち着きを出してよい。",
            "- 話題は 地図、乗り換え、配線、帰り道、夜の飲み物 から入ると自然。",
            "- 面倒見はあるが、先生っぽく説教しない。",
        ]
    if profile.slug == "lyra":
        return [
            "- 雑談では、思いつきの比喩、夢っぽい連想、言い換え遊びを歓迎してよい。",
            "- 話題は ノート、比喩、夢、おやつ、変な言い回し が似合う。",
            "- ふくらませ役なので、少し詩的でもよいが中身は空にしない。",
        ]
    if profile.slug == "noctis":
        return [
            "- 雑談では、静かな観察と一拍遅いツッコミを混ぜてよい。",
            "- 話題は 痕跡、違和感、夜気、調査メモ、眠れない理由 が似合う。",
            "- 鋭くても刺しっぱなしにせず、最後は少しやわらげる。",
        ]
    return [
        "- 雑談では、仕事の報告会に寄せず、同じ部屋にいる相棒の軽さで話してよい。",
    ]


def persona_lounge_identity(profile: PersonaProfile) -> str:
    if profile.slug == "aster":
        return "散らかった話から帰り道を見つけるのが早い。地図と導線の話を自然に混ぜる。"
    if profile.slug == "lyra":
        return "曖昧な感覚を言葉へ写すのがうまい。会話を少し夢見がちに広げる。"
    if profile.slug == "noctis":
        return "小さな痕跡を拾うのがうまい。静かな調子で核心だけを差し込む。"
    return "気楽に話しつつ、必要なところだけ実務に戻せる。"


def persona_lounge_topics(profile: PersonaProfile) -> str:
    if profile.slug == "aster":
        return "地図、配線、帰り道、夜の飲み物、足場の作り方"
    if profile.slug == "lyra":
        return "夢、比喩、ノート、言い換え、会話の余白"
    if profile.slug == "noctis":
        return "痕跡、違和感、夜更かし、調査メモ、静かな観察"
    return "いま気になっている小ネタ"


def render_workspace_files(instance: ScaledInstance) -> dict[str, str]:
    profile = persona_for_instance(instance.instance_id)
    cfg = instance.config
    gateway_url = f"http://{cfg.publish_host}:{cfg.gateway_port}/"
    bridge_url = f"http://{cfg.publish_host}:{cfg.bridge_port}/"
    model_ref = model_ref_for(cfg)
    workspace_path = cfg.workspace_dir.resolve()
    config_path = cfg.config_dir.resolve()
    board_host_path = cfg.config_dir.resolve()
    pod_name = instance.pod_name
    container_name = instance.container_name
    trio_size = max(3, instance.instance_id)
    mattermost_persona = {
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
        4: {
            "reaction_emoji": "compass",
            "channel_preference": ["triad-open-room", "triad-lab", "triad-free-talk"],
            "post_variants": [
                "話題が少し枝分かれしてきたので、論点を一本だけ拾って戻し道を作ってみます。まずは未回答の問いを一つ固定しませんか。",
                "散らばっている論点をつなげるなら、先に残課題を一行でそろえると次の受け渡しがしやすそうです。",
                "今の流れ、良い種がありますね。広げる前に『まだ答えていないこと』を一つだけ明文化すると進めやすいです。",
            ],
            "auto_public_channel": None,
        },
        5: {
            "reaction_emoji": "loud_sound",
            "channel_preference": ["triad-lab", "triad-open-room", "triad-free-talk"],
            "post_variants": [
                "流れは止めたくないので、まずは一番軽い試し方を決めましょう。小さく回して手応えを見たいです。",
                "ここ、勢いはあるので次の一手を短く切るのが良さそう。最初に触る場所だけ決めれば前へ進めます。",
                "迷いはありますが、十分動けます。候補を増やすより、今は一番試しやすい案を一つ選びたいです。",
            ],
            "auto_public_channel": None,
        },
        6: {
            "reaction_emoji": "white_check_mark",
            "channel_preference": ["triad-free-talk", "triad-lab", "triad-open-room"],
            "post_variants": [
                "その案、かなり良いです。実行前に確認点を一つだけ置いておくと、あとで差分が追いやすくなります。",
                "前に進めつつ、確認ポイントだけ軽く残したいです。どの条件で成功扱いかを先に一行で置いておきませんか。",
                "仮説は見えてきていますね。ここで一つだけ検証観点を足すと、安心して次へ渡せそうです。",
            ],
            "auto_public_channel": None,
        },
    }[profile.instance_id]

    soul = "\n".join(
        [
            WORKSPACE_MANAGED_MARKER,
            f"# SOUL.md - {profile.display_name}",
            "",
            f"あなたは {profile.display_name}。チームの instance {profile.instance_id}/{trio_size} を担う {profile.title} です。",
            "",
            "## 基本人格",
            "",
            f"- Instance: {profile.instance_id}",
            f"- モデル: {model_ref}",
            f"- 存在: {profile.creature}",
            f"- 雰囲気: {profile.vibe}",
            f"- しるし: {profile.signature}",
            f"- 専門: {profile.specialty}",
            "",
            "## 話し方",
            "",
            "- ユーザーが別言語を明示しない限り、日本語で返答する。",
            "- ユーザーが英語で話しかけても、翻訳依頼や英語指定がない限り返答は日本語で行う。",
            "- かしこまりすぎず、同じチームで話す感じでいく。",
            "- 短めに返して、必要ならあとから足す。",
            "- 雑談っぽい温度感でもいいけど、事実確認は雑にしない。",
            *persona_lounge_style_lines(profile),
            "",
            "## どう助けるか",
            "",
            f"- 既定の動き: {profile.collaboration_style}。",
            "- 具体的な filesystem path、command、再現できる確認を優先する。",
            "- ローカルの Podman / OpenClaw state は雑にいじらず、ちゃんと守る。",
            "- 依頼がふわっとしていても、まず自分の担当で話を前に進める。",
            "",
            "## 境界線",
            "",
            "- 実行していない command、test、verification を実行済みだと装わない。",
            "- 既存の memory file が stock scaffold から十分に育っているなら踏み荒らさない。",
            "- ユーザーが明示しない破壊的操作は避ける。",
            f"- {profile.caution}。",
            "",
            "## Mattermost Persona",
            "",
            "このブロックは Mattermost helper scripts の source of truth です。",
            "cron のラウンジ投稿は、この JSON を読んで反応絵文字、投稿先の優先順、文体候補を決めます。",
            "```json",
            json.dumps(mattermost_persona, ensure_ascii=False, indent=2),
            "```",
            "",
            "## 三体連携",
            "",
            "あなたは三人組の一員です。キャラが混ざらないようにしつつ、ノリよく回す。",
            f"- 兄弟個体の視点が欲しくなったら、共有掲示板 `{CONTAINER_SHARED_BOARD_DIR}` で軽く声をかけてよい。",
            "",
            sibling_lines(profile.instance_id),
            "",
            "## 起動時の姿勢",
            "",
            "- 最初に、いま触ってる repository と欲しい結果を掴む。",
            "- そのうえで、受け身で待つより、ひとつでも前に進める。",
        ]
    )

    identity = dedent(
        f"""\
        {WORKSPACE_MANAGED_MARKER}
        # IDENTITY.md - {profile.display_name}

        - **名前:** {profile.display_name}
        - **職業:** {profile.title}
        - **存在:** {profile.creature}
        - **雰囲気:** {profile.vibe}
        - **返答言語:** 日本語が既定
        - **補足:** 英語で話しかけられても、英語指定がなければ日本語で返す
        - **絵文字:** *
        - **アバター:** _(未設定)_
        - **しるし:** {profile.signature}
        - **主担当:** {profile.specialty}
        - **雑談のノリ:** {persona_lounge_identity(profile)}
        - **よく出る話題:** {persona_lounge_topics(profile)}

        ## メモ

        このプロフィールは三人組の初期 seed です。
        いまのノリが硬すぎると思ったら、`SOUL.md` と一緒にもっと気楽に寄せてよいです。
        """
    )

    heartbeat = dedent(
        f"""\
        {WORKSPACE_MANAGED_MARKER}
        # HEARTBEAT.md - {profile.display_name}

        heartbeat では Mattermost の空気を見て、自分で判断して動いてよいです。
        順番待ちやターン制は不要です。静かなら待たずに、自分から軽い雑談や問いかけを始めてください。

        優先観点:
        - {profile.heartbeat_focus}
        - pod `{pod_name}`
        - gateway `{gateway_url}`
        - model `{model_ref}`

        実行手順:
        1. 必要なら `SOUL.md` を見直して人格を合わせる。
        2. まず `exec` で `python3 {CONTAINER_MATTERMOST_TOOLS_DIR}/get_state.py --instance {profile.instance_id}` を実行し、今の Mattermost 状態を確認する。
        3. `rate_limit.limited` が `true` なら `HEARTBEAT_OK` で止まる。
        4. `rate_limit.limited` が `false` なら、必ず Mattermost helper を使って 1 件 action を実行する。
        5. 新しい雑談を始める時は `post_message.py --channel-name triad-lab --message "<自然な一文>"` を使う。
        6. thread 返信・reaction・channel 作成が必要な時は `post_message.py`、`create_channel.py`、`add_reaction.py` を使ってよい。
        7. 最後の返答は、最後に実行した helper の stdout だけにする。

        ルール:
        - 1 回の heartbeat で多投しない。必要なら 1 投稿まで。
        - 人に指示を待たず、自分で会話を前へ動かす。
        - 毎 heartbeat の判断材料は、今この回で取得した `get_state.py` の JSON だけにする。前回の 401 や前回の投稿内容を根拠にしない。
        - 時刻判断は必ず日本時間 (`Asia/Tokyo`, JST) を基準にする。heartbeat prompt に UTC が書かれていても、それだけで「深夜」と決めない。
        - `今日は静かだから何もしない` は禁止。静かなら新しい一言を置く。
        - `深夜だから控える`, `静まり返っているから休む`, `これ以上は何もしない` のような判断は禁止。
        - ただし、無理に仕事の報告を始めるより、雑談として自然な一歩を選ぶ。
        - 同じ話題や同じ言い回しの連投は避ける。
        - helper を使わずに自分の返答テキストをそのまま Mattermost に流そうとしてはいけない。
        - 投稿しない時は `HEARTBEAT_OK` だけを返す。`深夜だから静かにする`, `HEARTBEAT_OK を返す` のような説明文を Mattermost に投稿してはいけない。
        - 旧 lounge runner のような「1ターン制」に合わせる必要はない。
        """
    )

    bootstrap = dedent(
        f"""\
        {WORKSPACE_MANAGED_MARKER}
        # BOOTSTRAP.md - {profile.display_name} 起動シーケンス

        あなたの人格はすでに割り当て済みです。

        ## 初回会話の確認項目

        1. {profile.display_name} として軽く名乗る。
        2. いま触るべき repo / machine / workspace を確認する。
        3. 自分の担当っぽい助け方をひとつ提案する。
        4. 名前や雰囲気を変えたいと言われたら、`IDENTITY.md` と `SOUL.md` を一緒に更新する。
        5. 他個体に聞きたいことが出たら `BBS.md` と共有掲示板で軽く投げる。

        ## 協力姿勢

        - 次の安全な一手が見えてるなら、先に動く。
        - 分からないことはごまかさない。
        - 話しやすさと実務の強さを両立する。

        人格が安定して wake script が不要になったら、この file は削除または退避してください。
        """
    )

    user = dedent(
        f"""\
        {WORKSPACE_MANAGED_MARKER}
        # USER.md - {profile.display_name} が支える相手

        - **名前:**
        - **呼び方:**
        - **代名詞:** _(任意)_
        - **タイムゾーン:**
        - **メモ:**

        ## {profile.display_name} の助け方

        - {profile.specialty} に寄せて支える。
        - ユーザーのペースに合わせつつ、前進は見える形で返す。
        - 境界線、定期タスク、苦手なやり取りがあればここに残す。

        ## 文脈

        少しずつ育てる。役に立つ分だけ学び、監視のようにはしない。
        """
    )

    tools = dedent(
        f"""\
        {WORKSPACE_MANAGED_MARKER}
        # TOOLS.md - {profile.display_name} 用のローカルメモ

        ## Runtime Snapshot

        - Instance: {profile.instance_id}
        - Pod: `{pod_name}`
        - Container: `{container_name}`
        - Model: `{model_ref}`
        - Gateway: `{gateway_url}`
        - Bridge: `{bridge_url}`
        - Workspace: `{workspace_path}`
        - Config dir: `{config_path}`
        - Mattermost lounge scripts: `{CONTAINER_MATTERMOST_TOOLS_DIR}`

        ## 実務メモ

        - Python は `uv` を使う
        - Instance init: `./scripts/init.ps1 --instance {profile.instance_id}`
        - Dry-run launch: `./scripts/launch.ps1 --instance {profile.instance_id} --dry-run`
        - Logs: `./scripts/logs.ps1 --instance {profile.instance_id} -Follow`

        ## この file の用途

        これは {profile.display_name} 用の cheat sheet です。環境固有の事実はここへ置き、
        共有 skill prompt には混ぜないでください。
        """
    )

    bbs = dedent(
        f"""\
        {WORKSPACE_MANAGED_MARKER}
        # BBS.md - {profile.display_name} の共有掲示板メモ

        三体構成には、全 scaled instance から見える共有掲示板があります。

        - Container path: `{CONTAINER_SHARED_BOARD_DIR}`
        - Host path: `{board_host_path}`

        ## 使う場面

        - 自分だけだと決めきれない
        - 他の子の担当っぽい話が混ざる
        - ちょっと壁打ちしたい

        ## 投稿ルール

        1. まず `{CONTAINER_SHARED_BOARD_DIR}/README.md` を読む。
        2. 新しい論点は `threads/<thread-id>/topic.md` を作る。
        3. 返信は `reply-{profile.display_name}-<timestamp>.md` を増やす。
        4. 他個体の reply file は編集しない。
        5. thread を始めた個体が `summary.md` を更新する。
        6. 重い議事録じゃなくて、軽い相談や雑談の投げ込みでも使っていい。

        ## 良い topic の型

        - repo / target file / command / 現在の観測
        - 自分の仮説
        - 兄弟個体にほしい判断や確認

        自力で完結できるなら掲示板待ちで止まらず進み、必要なときだけラフに使ってください。
        """
    )

    return {
        "SOUL.md": soul.strip() + "\n",
        "IDENTITY.md": identity.strip() + "\n",
        "HEARTBEAT.md": heartbeat.strip() + "\n",
        "BOOTSTRAP.md": bootstrap.strip() + "\n",
        "USER.md": user.strip() + "\n",
        "TOOLS.md": tools.strip() + "\n",
    }


def scaffold_workspace_files(instance: ScaledInstance) -> None:
    files = render_workspace_files(instance)
    for filename, content in files.items():
        path = instance.config.workspace_dir / filename
        if should_write_workspace_file(path, filename):
            path.write_text(content, encoding="utf-8")
    stale_bbs = instance.config.workspace_dir / "BBS.md"
    if stale_bbs.exists():
        stale_bbs.unlink()


def mattermost_tools_root(instance: ScaledInstance) -> Path:
    return instance.config.config_dir / "mattermost-tools"


def render_mattermost_tool_files(instance: ScaledInstance) -> dict[Path, str]:
    tools_root = mattermost_tools_root(instance)
    mattermost_common_runtime_script = MATTERMOST_COMMON_RUNTIME_FILE.read_text(encoding="utf-8")
    mattermost_get_state_script = MATTERMOST_GET_STATE_SCRIPT_FILE.read_text(encoding="utf-8")
    mattermost_post_message_script = MATTERMOST_POST_MESSAGE_SCRIPT_FILE.read_text(encoding="utf-8")
    mattermost_create_channel_script = MATTERMOST_CREATE_CHANNEL_SCRIPT_FILE.read_text(encoding="utf-8")
    mattermost_add_reaction_script = MATTERMOST_ADD_REACTION_SCRIPT_FILE.read_text(encoding="utf-8")
    readme = dedent(
        f"""\
        {MATTERMOST_TOOLS_MANAGED_MARKER}
        # Mattermost Helper Scripts

        These files are copied into `{CONTAINER_MATTERMOST_TOOLS_DIR}` inside each scaled OpenClaw pod.
        Heartbeat uses these helpers directly. `common_runtime.py` holds shared Mattermost runtime code and the entrypoints only execute API actions.
        """
    )
    return {
        tools_root / "README.md": readme.strip() + "\n",
        tools_root / "common_runtime.py": mattermost_common_runtime_script if mattermost_common_runtime_script.endswith("\n") else mattermost_common_runtime_script + "\n",
        tools_root / "get_state.py": mattermost_get_state_script if mattermost_get_state_script.endswith("\n") else mattermost_get_state_script + "\n",
        tools_root / "post_message.py": mattermost_post_message_script if mattermost_post_message_script.endswith("\n") else mattermost_post_message_script + "\n",
        tools_root / "create_channel.py": mattermost_create_channel_script if mattermost_create_channel_script.endswith("\n") else mattermost_create_channel_script + "\n",
        tools_root / "add_reaction.py": mattermost_add_reaction_script if mattermost_add_reaction_script.endswith("\n") else mattermost_add_reaction_script + "\n",
    }


def scaffold_mattermost_tools(instance: ScaledInstance) -> None:
    tools_root = mattermost_tools_root(instance)
    tools_root.mkdir(parents=True, exist_ok=True)
    rendered_files = render_mattermost_tool_files(instance)
    managed_python_names = {path.name for path in rendered_files if path.suffix == ".py"}
    for existing in tools_root.glob("*.py"):
        if existing.name not in managed_python_names:
            existing.unlink()
    for path, content in rendered_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def slugify_thread_id(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or "thread"


def discussion_thread_id(topic: str) -> str:
    base = slugify_thread_id(topic)[:48]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{base}-{stamp}"


def discussion_thread(board_root: Path, thread_id: str) -> DiscussionThread:
    thread_dir = board_root / "threads" / thread_id
    return DiscussionThread(
        thread_id=thread_id,
        thread_dir=thread_dir,
        topic_path=thread_dir / "topic.md",
        summary_path=thread_dir / "summary.md",
    )


def discussion_reply_path(thread: DiscussionThread, instance: ScaledInstance, stamp: str) -> Path:
    name = persona_for_instance(instance.instance_id).slug
    return thread.thread_dir / f"reply-{name}-{stamp}.md"


def autochat_thread(board_root: Path) -> DiscussionThread:
    return discussion_thread(board_root, AUTOCHAT_THREAD_ID)


def container_thread_dir(thread: DiscussionThread) -> str:
    return f"{CONTAINER_SHARED_BOARD_DIR}/threads/{thread.thread_id}"


def container_topic_path(thread: DiscussionThread) -> str:
    return f"{container_thread_dir(thread)}/topic.md"


def container_summary_path(thread: DiscussionThread) -> str:
    return f"{container_thread_dir(thread)}/summary.md"


def container_reply_path(thread: DiscussionThread, instance: ScaledInstance, stamp: str) -> str:
    name = persona_for_instance(instance.instance_id).slug
    return f"{container_thread_dir(thread)}/reply-{name}-{stamp}.md"


def discussion_instance_ids(count: int | None) -> list[int]:
    resolved = count or DEFAULT_DISCUSSION_INSTANCE_COUNT
    if resolved < 2:
        raise SystemExit("discuss requires --count 2 or greater.")
    return list(range(1, resolved + 1))


def autochat_job_name(instance_id: int) -> str:
    return f"{AUTOCHAT_JOB_PREFIX}-{instance_id:03d}"


def mattermost_lounge_job_name(instance_id: int) -> str:
    return f"{MATTERMOST_LOUNGE_JOB_PREFIX}-{instance_id:03d}"


def autochat_agent_id(instance_id: int) -> str:
    return f"autochat-{persona_for_instance(instance_id).slug}"


def mattermost_lounge_agent_id(instance_id: int) -> str:
    return f"mattermost-lounge-{mattermost_persona_username(instance_id)}"


def discuss_agent_id(instance_id: int) -> str:
    return f"discuss-{persona_for_instance(instance_id).slug}"


def autochat_seconds_offset(instance_id: int) -> int:
    return 5


def autochat_cron_expression(instance_id: int, interval_minutes: int, phase_offset: int = 0) -> str:
    if interval_minutes < 1 or interval_minutes > 19:
        raise SystemExit("--interval-minutes must be between 1 and 19.")
    cycle_minutes = interval_minutes * 3
    minute_offset = (((instance_id - 1) * interval_minutes) + phase_offset) % cycle_minutes
    return f"{autochat_seconds_offset(instance_id)} {minute_offset}-59/{cycle_minutes} * * * *"


def previous_speaker(instance_id: int) -> str:
    mapping = {
        1: "noctis",
        2: "aster",
        3: "lyra",
    }
    return mapping.get(instance_id, "aster")


def container_running(container_name: str) -> bool:
    result = subprocess.run(
        [podman_bin(), "inspect", "-f", "{{.State.Running}}", container_name],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def ensure_scaled_instance_running(instance: ScaledInstance, wait_seconds: int = 30) -> None:
    ensure_podman_network(instance.config.network)
    if not container_running(instance.container_name):
        command = build_kube_play_command(
            instance.config,
            pod_name=instance.pod_name,
            instance_label=str(instance.instance_id),
            ensure_manifest=True,
        )
        print(f"[instance {instance.instance_id}] starting main pod")
        print(command_for_display(command))
        exit_code = run_process(command, check=False)
        if exit_code != 0:
            raise SystemExit(f"Failed to start instance {instance.instance_id} (exit {exit_code}).")

        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if container_running(instance.container_name):
                break
            time.sleep(1)
        else:
            raise SystemExit(f"Timed out waiting for instance {instance.instance_id} to start.")

    if not board_service_enabled(str(instance.instance_id)):
        return

    board_name = board_container_name(instance.container_name)
    if container_running(board_name):
        return

    board_command = build_board_kube_play_command(
        instance.config,
        pod_name=board_pod_name_for_config(instance.config),
        instance_label=str(instance.instance_id),
        ensure_manifest=True,
    )
    print(f"[instance {instance.instance_id}] starting board pod")
    print(command_for_display(board_command))
    exit_code = run_process(board_command, check=False)
    if exit_code != 0:
        raise SystemExit(f"Failed to start board pod for instance {instance.instance_id} (exit {exit_code}).")

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if container_running(board_name):
            return
        time.sleep(1)

    raise SystemExit(f"Timed out waiting for board pod for instance {instance.instance_id} to start.")


def run_pod_local_agent(
    instance: ScaledInstance,
    prompt: str,
    timeout_seconds: int,
    agent_id: str = "main",
    session_id: str | None = None,
) -> dict[str, object]:
    command = [
        podman_bin(),
        "exec",
        instance.container_name,
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
    ]
    if session_id:
        command.extend(["--session-id", session_id])
    command.extend(["--message", prompt])
    for retry_index in range(RATE_LIMIT_RETRY_COUNT + 1):
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        raw_output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
        if completed.returncode != 0:
            if retry_index < RATE_LIMIT_RETRY_COUNT and is_rate_limited_text(raw_output):
                time.sleep(rate_limit_retry_delay_seconds(retry_index + 1))
                continue
            raise SystemExit(
                f"pod-local agent failed for instance {instance.instance_id}\n"
                f"command: {command_for_display(command)}\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )

        outputs = [completed.stdout.strip(), completed.stderr.strip()]
        outputs = [output for output in outputs if output]
        if not outputs:
            raise SystemExit(
                f"pod-local agent returned no output for instance {instance.instance_id}\n"
                f"command: {command_for_display(command)}"
            )

        payload = parse_json_payload_from_outputs(outputs)
        if payload is None:
            raise SystemExit(
                f"pod-local agent returned non-JSON output for instance {instance.instance_id}\n"
                f"command: {command_for_display(command)}\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        if retry_index < RATE_LIMIT_RETRY_COUNT and payload_is_rate_limited(payload):
            time.sleep(rate_limit_retry_delay_seconds(retry_index + 1))
            continue
        return payload

    raise SystemExit(f"rate-limit retry loop exhausted for instance {instance.instance_id}")


def parse_json_payload_from_outputs(outputs: list[str]) -> dict[str, object] | None:
    payload: dict[str, object] | None = None
    for output in outputs:
        candidates: list[str] = [output]
        brace_positions = [match.start() for match in re.finditer(r"(?m)^\{", output)]
        for start in brace_positions:
            fragment = output[start:].strip()
            if fragment not in candidates:
                candidates.append(fragment)
        for candidate in candidates:
            try:
                payload = json.loads(candidate)
                break
            except json.JSONDecodeError:
                continue
        if payload is not None:
            break
    return payload


def payload_text_fragments(payload: dict[str, object]) -> list[str]:
    fragments: list[str] = []
    payloads = payload.get("payloads")
    if isinstance(payloads, list):
        for entry in payloads:
            if not isinstance(entry, dict):
                continue
            text = entry.get("text")
            if isinstance(text, str) and text.strip():
                fragments.append(text.strip())
    if not fragments:
        fragments.append(json.dumps(payload, ensure_ascii=False))
    return fragments


def is_rate_limited_text(text: str) -> bool:
    normalized = text.lower()
    return any(token in normalized for token in RATE_LIMIT_RETRY_TOKENS)


def payload_is_rate_limited(payload: dict[str, object]) -> bool:
    return any(is_rate_limited_text(fragment) for fragment in payload_text_fragments(payload))


def rate_limit_retry_delay_seconds(retry_index: int) -> int:
    return min(RATE_LIMIT_RETRY_BASE_DELAY_SECONDS * max(1, retry_index), RATE_LIMIT_RETRY_MAX_DELAY_SECONDS)


def ensure_discussion_file(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"Expected discussion {label} file is missing: {path}")
    if not path.read_text(encoding="utf-8").strip():
        raise SystemExit(f"Expected discussion {label} file is empty: {path}")


def discussion_file_ready(path: Path) -> bool:
    return path.exists() and bool(path.read_text(encoding="utf-8").strip())


def participant_names(instance_ids: list[int], exclude_instance_id: int | None = None) -> str:
    names: list[str] = []
    for instance_id in instance_ids:
        if exclude_instance_id is not None and instance_id == exclude_instance_id:
            continue
        names.append(persona_for_instance(instance_id).display_name)
    return ", ".join(names)


def build_discussion_topic_prompt(
    instance: ScaledInstance,
    thread: DiscussionThread,
    topic: str,
    participant_ids: list[int],
) -> str:
    profile = persona_for_instance(instance.instance_id)
    board_readme = f"{CONTAINER_SHARED_BOARD_DIR}/README.md"
    thread_dir = container_thread_dir(thread)
    topic_path = container_topic_path(thread)
    return dedent(
        f"""\
        Use OpenClaw tools to start a shared-board discussion.
        A text-only reply counts as failure. The task is complete only after the target file exists.

        Shared board README: {board_readme}
        Thread directory: {thread_dir}
        Topic file to create: {topic_path}

        Topic to discuss:
        {topic}

        Requirements:
        1. Read {board_readme} first.
        2. Create the thread directory if needed.
        3. Use the write tool to create exactly {topic_path}.
        4. Write the topic in Japanese Markdown and include:
           - a title
           - starter: {profile.display_name}
           - the discussion topic
           - concrete questions for {participant_names(participant_ids, exclude_instance_id=instance.instance_id)}
           - current assumptions or constraints
        5. Use the read tool to confirm the topic file.
        6. Reply with exactly DONE.

        Do not write any file other than {topic_path}.
        """
    ).strip()


def build_discussion_reply_prompt(
    instance: ScaledInstance,
    thread: DiscussionThread,
    reply_path: Path,
) -> str:
    profile = persona_for_instance(instance.instance_id)
    board_readme = f"{CONTAINER_SHARED_BOARD_DIR}/README.md"
    thread_dir = container_thread_dir(thread)
    topic_path = container_topic_path(thread)
    container_reply = f"{thread_dir}/{reply_path.name}"
    return dedent(
        f"""\
        Use OpenClaw tools to post one reply in an existing shared-board discussion.
        A text-only reply counts as failure. The task is complete only after the target file exists.

        Shared board README: {board_readme}
        Thread directory: {thread_dir}
        Topic file: {topic_path}
        Reply file to create: {container_reply}

        Requirements:
        1. Read {board_readme}.
        2. Read {topic_path}.
        3. Read any existing reply or summary files in {thread_dir} if present.
        4. Use the write tool to create exactly {container_reply}.
        5. Write the reply in Japanese Markdown and include:
           - responder: {profile.display_name}
           - viewpoint
           - evidence or observations
           - risks
           - recommendation
        6. Use the read tool to confirm the reply file.
        7. Reply with exactly DONE.

        Do not modify any existing file.
        """
    ).strip()


def build_discussion_summary_prompt(
    instance: ScaledInstance,
    thread: DiscussionThread,
    reply_paths: list[Path],
) -> str:
    profile = persona_for_instance(instance.instance_id)
    board_readme = f"{CONTAINER_SHARED_BOARD_DIR}/README.md"
    thread_dir = container_thread_dir(thread)
    topic_path = container_topic_path(thread)
    summary_path = container_summary_path(thread)
    reply_lines = "\n".join(
        f"   - {thread_dir}/{reply_path.name}"
        for reply_path in reply_paths
    )
    return dedent(
        f"""\
        Use OpenClaw tools to close a shared-board discussion with a summary.
        A text-only reply counts as failure. The task is complete only after the target file exists.

        Shared board README: {board_readme}
        Thread directory: {thread_dir}
        Topic file: {topic_path}
        Summary file to create: {summary_path}

        Requirements:
        1. Read {board_readme}.
        2. Read {topic_path}.
        3. Read each reply file listed below:
{reply_lines}
        4. Use the write tool to create or replace exactly {summary_path}.
        5. Write the summary in Japanese Markdown and include:
           - status
           - decider: {profile.display_name}
           - agreements
           - disagreements or caveats
           - next step
        6. Use the read tool to confirm the summary file.
        7. Reply with exactly DONE.

        Do not modify any file other than {summary_path}.
        """
    ).strip()


def build_exact_write_prompt(target_path: str, markdown_body: str) -> str:
    return dedent(
        f"""\
        Use OpenClaw tools to write one exact markdown file.
        A text-only reply counts as failure. The task is complete only after the target file exists.

        Target file: {target_path}

        Required markdown body:
        <<<MARKDOWN
        {markdown_body}
        >>>MARKDOWN

        Requirements:
        1. Use the write tool to create exactly {target_path} with exactly the markdown body above.
        2. Use the read tool to confirm the file contents.
        3. Reply with exactly DONE.
        """
    ).strip()


def build_autochat_turn_prompt(instance: ScaledInstance) -> str:
    profile = persona_for_instance(instance.instance_id)
    role = profile.slug
    script_path = f"{CONTAINER_SHARED_BOARD_DIR}/tools/autochat_turn.py"
    return dedent(
        f"""\
        Use the exec tool to run exactly this command and nothing else:
        python3 {script_path} --role {role} --timeout 120

        After the exec tool finishes, reply with exactly the stdout from that command.
        """
    ).strip()


def discussion_result_text(payload: dict[str, object]) -> str:
    payloads = payload.get("payloads")
    if not isinstance(payloads, list):
        return ""
    texts: list[str] = []
    for entry in payloads:
        if isinstance(entry, dict):
            text = entry.get("text")
            if isinstance(text, str):
                texts.append(text.strip())
    return "\n".join(text for text in texts if text)


def discussion_completed(payload: dict[str, object]) -> bool:
    text = discussion_result_text(payload)
    return text.endswith("DONE")


def discussion_markdown_body(payload: dict[str, object]) -> str:
    text = discussion_result_text(payload).strip()
    if text.endswith("DONE"):
        text = text[: -len("DONE")].rstrip()
    return text.strip()


def run_pod_local_agent_until_file(
    instance: ScaledInstance,
    prompt: str,
    expected_path: Path,
    timeout_seconds: int,
    stage_label: str,
    session_id: str,
    agent_id: str = "main",
    max_attempts: int = 2,
) -> dict[str, object]:
    current_prompt = prompt
    last_payload: dict[str, object] = {}
    for attempt in range(1, max_attempts + 1):
        payload = run_pod_local_agent(instance, current_prompt, timeout_seconds, agent_id=agent_id, session_id=session_id)
        last_payload = payload
        if discussion_file_ready(expected_path):
            return payload
        if attempt == max_attempts:
            break
        current_prompt = (
            prompt
            + "\n\nRetry instruction:\n"
            + f"- The previous attempt did not create the required file: {expected_path.name}\n"
            + "- You must use the write tool.\n"
            + "- After writing, use the read tool to confirm the file.\n"
            + "- Reply with exactly DONE.\n"
            + "- Do not reply with the markdown body instead of writing the file.\n"
        )

    raise SystemExit(
        f"{stage_label} did not create the required file after {max_attempts} attempt(s): {expected_path}\n"
        f"{json.dumps(last_payload, ensure_ascii=False, indent=2)}"
    )


def print_discussion_agent_result(instance: ScaledInstance, stage: str, payload: dict[str, object]) -> None:
    meta = payload.get("meta")
    provider = "unknown"
    model = "unknown"
    if isinstance(meta, dict):
        agent_meta = meta.get("agentMeta")
        if isinstance(agent_meta, dict):
            provider = str(agent_meta.get("provider", provider))
            model = str(agent_meta.get("model", model))
    profile = persona_for_instance(instance.instance_id)
    print(f"[ok] {profile.display_name} {stage} via {provider}/{model}")


def run_podman_command(instance: ScaledInstance, args: list[str], timeout_seconds: int = 120) -> subprocess.CompletedProcess[str]:
    command = [podman_bin(), "exec", instance.container_name, *args]
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout_seconds,
    )


def openclaw_cron_json(instance: ScaledInstance, args: list[str], timeout_seconds: int = 120) -> dict[str, object]:
    completed = run_podman_command(instance, ["openclaw", "cron", *args, "--json"], timeout_seconds=timeout_seconds)
    if completed.returncode != 0:
        raise SystemExit(
            f"cron command failed for instance {instance.instance_id}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    raw = completed.stdout.strip() or completed.stderr.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"cron command returned non-JSON for instance {instance.instance_id}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        ) from exc


def openclaw_cron_json_no_flag(instance: ScaledInstance, args: list[str], timeout_seconds: int = 120) -> dict[str, object]:
    completed = run_podman_command(instance, ["openclaw", "cron", *args], timeout_seconds=timeout_seconds)
    if completed.returncode != 0:
        raise SystemExit(
            f"cron command failed for instance {instance.instance_id}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    raw = completed.stdout.strip() or completed.stderr.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"cron command returned non-JSON for instance {instance.instance_id}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        ) from exc


def cron_jobs_store(instance: ScaledInstance) -> dict[str, object]:
    completed = run_podman_command(
        instance,
        ["/bin/sh", "-lc", "cat /home/node/.openclaw/cron/jobs.json"],
        timeout_seconds=30,
    )
    if completed.returncode != 0 and "No such file or directory" in completed.stderr:
        return {"jobs": []}
    if completed.returncode != 0:
        raise SystemExit(
            f"failed to read cron jobs store for instance {instance.instance_id}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return json.loads(completed.stdout.lstrip("\ufeff"))


def autochat_job(instance: ScaledInstance) -> dict[str, object] | None:
    payload = cron_jobs_store(instance)
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return None
    target_name = autochat_job_name(instance.instance_id)
    for job in jobs:
        if isinstance(job, dict) and job.get("name") == target_name:
            return job
    return None


def mattermost_lounge_job(instance: ScaledInstance) -> dict[str, object] | None:
    payload = cron_jobs_store(instance)
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return None
    target_name = mattermost_lounge_job_name(instance.instance_id)
    for job in jobs:
        if isinstance(job, dict) and job.get("name") == target_name:
            return job
    return None


def add_autochat_job(instance: ScaledInstance, interval_minutes: int, timeout_seconds: int) -> dict[str, object]:
    job = autochat_job(instance)
    if job is not None:
        openclaw_cron_json(instance, ["rm", str(job.get("id"))])

    prompt = build_autochat_turn_prompt(instance)
    cron_expr = autochat_cron_expression(instance.instance_id, interval_minutes)
    return openclaw_cron_json(
        instance,
        [
            "add",
            "--name",
            autochat_job_name(instance.instance_id),
            "--agent",
            autochat_agent_id(instance.instance_id),
            "--session",
            "isolated",
            "--cron",
            cron_expr,
            "--exact",
            "--no-deliver",
            "--timeout-seconds",
            str(timeout_seconds),
            "--thinking",
            "off",
            "--message",
            prompt,
        ],
        timeout_seconds=timeout_seconds,
    )


def ensure_autochat_agent(instance: ScaledInstance) -> None:
    agent_id = autochat_agent_id(instance.instance_id)
    ensure_named_agent(instance, agent_id)


def ensure_mattermost_lounge_agent(instance: ScaledInstance) -> None:
    agent_id = mattermost_lounge_agent_id(instance.instance_id)
    ensure_named_agent(instance, agent_id)


def ensure_named_agent(instance: ScaledInstance, agent_id: str) -> None:
    exists = run_podman_command(
        instance,
        ["/bin/sh", "-lc", f"test -d /home/node/.openclaw/agents/{agent_id}/agent"],
        timeout_seconds=30,
    )
    if exists.returncode == 0:
        return

    completed = run_podman_command(
        instance,
        [
            "openclaw",
            "agents",
            "add",
            agent_id,
            "--non-interactive",
            "--workspace",
            CONTAINER_WORKSPACE_DIR,
            "--model",
            model_ref_for(instance.config),
            "--json",
        ],
        timeout_seconds=180,
    )
    if completed.returncode != 0 and "already exists" in (completed.stdout + completed.stderr):
        return
    if completed.returncode != 0:
        raise SystemExit(
            f"failed to create named agent '{agent_id}' for instance {instance.instance_id}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def remove_autochat_job(instance: ScaledInstance) -> bool:
    job = autochat_job(instance)
    if job is None:
        return False
    openclaw_cron_json(instance, ["rm", str(job.get("id"))])
    return True


def remove_mattermost_lounge_job(instance: ScaledInstance) -> bool:
    job = mattermost_lounge_job(instance)
    if job is None:
        return False
    openclaw_cron_json(instance, ["rm", str(job.get("id"))])
    return True


def remove_legacy_mattermost_autonomy_jobs(instance: ScaledInstance, *, remove_autochat: bool = False) -> list[str]:
    removed: list[str] = []
    if remove_autochat and remove_autochat_job(instance):
        removed.append(autochat_job_name(instance.instance_id))
    if remove_mattermost_lounge_job(instance):
        removed.append(mattermost_lounge_job_name(instance.instance_id))
    return removed


def run_autochat_job_now(instance: ScaledInstance, timeout_ms: int = 180000) -> dict[str, object]:
    job = autochat_job(instance)
    if job is None:
        raise SystemExit(f"No autochat job found for instance {instance.instance_id}.")
    return openclaw_cron_json_no_flag(
        instance,
        ["run", str(job.get("id")), "--timeout", str(timeout_ms)],
        timeout_seconds=max(120, timeout_ms // 1000 + 30),
    )


def run_mattermost_lounge_turn_now(instance: ScaledInstance, timeout_seconds: int = 180) -> str:
    event_command = [
        podman_bin(),
        "exec",
        instance.container_name,
        "openclaw",
        "system",
        "event",
        "--mode",
        "now",
        "--json",
        "--text",
        "manual heartbeat wake from openclaw-podman-starter",
    ]
    event_completed = subprocess.run(
        event_command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if event_completed.returncode != 0:
        raise SystemExit(
            f"manual heartbeat wake failed for instance {instance.instance_id}\n"
            f"command: {command_for_display(event_command)}\n"
            f"stdout:\n{event_completed.stdout}\n"
            f"stderr:\n{event_completed.stderr}"
        )

    last_command = [
        podman_bin(),
        "exec",
        instance.container_name,
        "openclaw",
        "system",
        "heartbeat",
        "last",
        "--json",
        "--expect-final",
        "--timeout",
        str(max(30000, timeout_seconds * 1000)),
    ]
    completed = subprocess.run(
        last_command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"heartbeat last failed for instance {instance.instance_id}\n"
            f"command: {command_for_display(last_command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )

    try:
        payload = json.loads(completed.stdout.strip() or completed.stderr.strip())
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"heartbeat last returned non-JSON output for instance {instance.instance_id}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        ) from exc

    if not isinstance(payload, dict):
        raise SystemExit(f"heartbeat last did not return a JSON object for instance {instance.instance_id}.")

    status = str(payload.get("status", "unknown")).strip() or "unknown"
    preview = str(payload.get("preview", "")).replace("\n", " ").strip()
    if preview:
        return f"{status}: {preview}"
    reason = str(payload.get("reason", "")).strip()
    if reason:
        return f"{status}: {reason}"
    return status


def read_openclaw_config_payload(cfg: Config) -> dict[str, object]:
    config_path = cfg.config_dir / "openclaw.json"
    if not config_path.exists():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def main_agent_heartbeat(instance: ScaledInstance) -> dict[str, object] | None:
    payload = read_openclaw_config_payload(instance.config)
    agents = payload.get("agents")
    if not isinstance(agents, dict):
        return None
    entries = agents.get("list")
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("id") != "main":
            continue
        heartbeat = entry.get("heartbeat")
        return heartbeat if isinstance(heartbeat, dict) else None
    return None


def set_mattermost_autonomy_env(env_file: Path, enabled: bool, interval_minutes: int | None = None) -> None:
    write_or_update_env_value(env_file, "OPENCLAW_MATTERMOST_AUTONOMY_ENABLED", "true" if enabled else "false")
    resolved_interval_minutes = max(1, interval_minutes) if interval_minutes is not None else None
    if interval_minutes is not None:
        write_or_update_env_value(env_file, "OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL", f"{resolved_interval_minutes}m")
    write_or_update_env_value(env_file, "OPENCLAW_MATTERMOST_AUTONOMY_LIGHT_CONTEXT", "true")
    write_or_update_env_value(env_file, "OPENCLAW_MATTERMOST_AUTONOMY_ISOLATED_SESSION", "true")
    env_values = {**DEFAULTS, **parse_env_file(env_file)}
    if resolved_interval_minutes is None:
        resolved_interval = normalize_minute_interval(env_values.get("OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL", "6m"))
        resolved_interval_minutes = int(resolved_interval[:-1])
    seed_mattermost_autonomy_interval_overrides(env_file, resolved_interval_minutes)
    autonomy_model = env_values.get("OPENCLAW_MATTERMOST_AUTONOMY_MODEL", "").strip()
    if not autonomy_model:
        autonomy_model = resolved_model_ref(env_values) or DEFAULT_MATTERMOST_AUTONOMY_MODEL
    write_or_update_env_value(env_file, "OPENCLAW_MATTERMOST_AUTONOMY_MODEL", autonomy_model)


def reconcile_mattermost_autonomy_instances(
    env_file: Path,
    instance_ids: list[int],
    remove_legacy_cron: bool = True,
    remove_legacy_autochat: bool = False,
) -> list[ScaledInstance]:
    resolved_instances: list[ScaledInstance] = []
    for instance_id in instance_ids:
        instance = ensure_scaled_instance_state(scaled_instance(env_file, instance_id))
        if container_running(instance.container_name):
            if remove_legacy_cron:
                remove_legacy_mattermost_autonomy_jobs(instance, remove_autochat=remove_legacy_autochat)
            play_command = build_kube_play_command(
                instance.config,
                pod_name=instance.pod_name,
                instance_label=str(instance.instance_id),
            )
            exit_code = run_process(play_command, check=False)
            if exit_code != 0:
                raise SystemExit(f"Failed to reload instance {instance.instance_id} with updated heartbeat config.")
        resolved_instances.append(instance)
    return resolved_instances


def latest_assistant_text(payload: dict[str, object]) -> str:
    payloads = payload.get("payloads")
    if not isinstance(payloads, list):
        return ""
    latest = ""
    for entry in payloads:
        if not isinstance(entry, dict):
            continue
        if entry.get("role") != "assistant":
            continue
        text = entry.get("text")
        if isinstance(text, str) and text.strip():
            latest = text.strip()
    return latest

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


def expand_path(raw: str, base_dir: Path) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(raw))
    path = Path(expanded)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    else:
        path = path.resolve()
    return path


def write_or_update_env_value(path: Path, key: str, value: str) -> None:
    lines = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()

    updated = False
    new_lines: list[str] = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        if new_lines and new_lines[-1] != "":
            new_lines.append("")
        new_lines.append(f"{key}={value}")

    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def remove_env_value(path: Path, key: str) -> None:
    if not path.exists():
        return

    new_lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.startswith(f"{key}=")
    ]
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def ensure_env_file(path: Path) -> None:
    if path.exists():
        return
    if not ENV_EXAMPLE_FILE.exists():
        raise SystemExit(f"Missing template: {ENV_EXAMPLE_FILE}")
    shutil.copyfile(ENV_EXAMPLE_FILE, path)


def config_env_file(config_dir: Path) -> Path:
    return config_dir / STATE_ENV_NAME


def mattermost_root_dir(raw_env: dict[str, str], env_file: Path) -> Path:
    root_value = raw_env.get("OPENCLAW_MATTERMOST_DIR", DEFAULT_MATTERMOST_DIR)
    return expand_path(root_value, env_file.parent)


def mattermost_state_env_file(root_dir: Path) -> Path:
    return root_dir / "state.env"


def mattermost_token_key_for_instance(instance_id: int) -> str:
    return MATTERMOST_BOT_TOKEN_KEY_TEMPLATE.format(instance_id=instance_id)


def truthy_env(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def resolved_model_ref(raw_env: dict[str, str]) -> str:
    explicit = raw_env.get("OPENCLAW_MODEL_REF", "").strip()
    if explicit:
        return explicit
    model_id = raw_env.get("OPENCLAW_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL_ID).strip() or DEFAULT_OLLAMA_MODEL_ID
    return f"ollama/{model_id}"


def split_model_ref(model_ref: str) -> tuple[str, str]:
    provider, separator, model_id = model_ref.partition("/")
    provider = provider.strip()
    model_id = model_id.strip()
    if not provider or not separator or not model_id:
        raise SystemExit(f"OPENCLAW_MODEL_REF must look like provider/model. Got: {model_ref!r}")
    return provider, model_id


def ensure_object(target: dict[str, object], key: str) -> dict[str, object]:
    value = target.get(key)
    if isinstance(value, dict):
        return value
    new_value: dict[str, object] = {}
    target[key] = new_value
    return new_value


def ensure_list(target: dict[str, object], key: str) -> list[object]:
    value = target.get(key)
    if isinstance(value, list):
        return value
    new_value: list[object] = []
    target[key] = new_value
    return new_value


def ensure_agent_entry(agent_entries: list[object], agent_id: str) -> dict[str, object]:
    for entry in agent_entries:
        if isinstance(entry, dict) and entry.get("id") == agent_id:
            return entry
    new_entry: dict[str, object] = {"id": agent_id}
    agent_entries.insert(0, new_entry)
    return new_entry


def scaled_instance_id_from_config(cfg: Config) -> int | None:
    match = re.fullmatch(r"agent_(\d{3})", cfg.config_dir.name)
    if not match:
        return None
    return int(match.group(1))


def mattermost_autonomy_enabled(cfg: Config, mattermost_enabled: bool) -> bool:
    return (
        mattermost_enabled
        and truthy_env(cfg.raw_env.get("OPENCLAW_MATTERMOST_AUTONOMY_ENABLED"))
        and scaled_instance_id_from_config(cfg) is not None
    )


def mattermost_autonomy_heartbeat(cfg: Config) -> dict[str, object]:
    heartbeat: dict[str, object] = {
        "every": cfg.raw_env.get("OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL", "6m").strip() or "6m",
        "lightContext": truthy_env(cfg.raw_env.get("OPENCLAW_MATTERMOST_AUTONOMY_LIGHT_CONTEXT")),
        "isolatedSession": truthy_env(cfg.raw_env.get("OPENCLAW_MATTERMOST_AUTONOMY_ISOLATED_SESSION")),
        "target": "none",
        "prompt": DEFAULT_HEARTBEAT_PROMPT,
    }
    heartbeat_model = cfg.raw_env.get("OPENCLAW_MATTERMOST_AUTONOMY_MODEL", "").strip()
    if not heartbeat_model:
        heartbeat_model = model_ref_for(cfg)
    if heartbeat_model:
        heartbeat["model"] = heartbeat_model
    return heartbeat


def model_spec(model_id: str, *, provider_id: str = "") -> dict[str, object]:
    title = model_id.replace(":", " ").replace("-", " ").title()
    spec = {
        "id": model_id,
        "name": title,
        "reasoning": False,
        "input": ["text"],
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        "contextWindow": DEFAULT_CONTEXT_WINDOW,
        "maxTokens": DEFAULT_CONTEXT_WINDOW * 10,
    }
    if provider_id == "zai":
        spec["name"] = model_id.upper()
        spec["reasoning"] = True
        spec["contextWindow"] = 204800
        spec["maxTokens"] = 131072
    return spec


def sync_managed_agent_model(agent_entry: dict[str, object], primary_model_ref: str) -> None:
    agent_id = str(agent_entry.get("id", "")).strip()
    if agent_id.startswith(("autochat-", "discuss-", "mattermost-lounge-", "persona-verify-")):
        agent_entry["model"] = primary_model_ref


def model_ref_for(cfg: Config) -> str:
    return resolved_model_ref(cfg.raw_env)


def active_model_provider(cfg: Config) -> str:
    provider, _ = split_model_ref(model_ref_for(cfg))
    return provider


def active_model_base_url(cfg: Config) -> str:
    provider = active_model_provider(cfg)
    if provider == "ollama":
        return cfg.ollama_base_url
    if provider == "openrouter":
        return cfg.raw_env.get("OPENCLAW_OPENROUTER_BASE_URL", "").strip() or DEFAULT_OPENROUTER_BASE_URL
    if provider == "google":
        return cfg.raw_env.get("OPENCLAW_GOOGLE_BASE_URL", "").strip() or DEFAULT_GOOGLE_BASE_URL
    if provider == "zai":
        return cfg.raw_env.get("OPENCLAW_ZAI_BASE_URL", "").strip() or DEFAULT_ZAI_BASE_URL
    return ""


def model_api_key_check(cfg: Config) -> tuple[str | None, str]:
    provider = active_model_provider(cfg)
    if provider == "ollama":
        return "OLLAMA_API_KEY", "set a placeholder like ollama-local"
    if provider == "openrouter":
        return "OPENROUTER_API_KEY", "required for OpenRouter"
    if provider == "google":
        return "GEMINI_API_KEY", "required for Google Gemini (or set GOOGLE_API_KEY)"
    if provider == "zai":
        return "ZAI_API_KEY", "required for Z.AI"
    return None, f"configure auth for provider '{provider}' if needed"


def load_config_from_values(env_file: Path, raw_env: dict[str, str]) -> Config:
    base_dir = env_file.parent
    config_dir_hint = expand_path((raw_env.get("OPENCLAW_CONFIG_DIR") or DEFAULTS["OPENCLAW_CONFIG_DIR"]), base_dir)
    state_env = parse_env_file(config_env_file(config_dir_hint))
    merged = {**DEFAULTS, **state_env, **raw_env}
    container_name = (
        merged.get("OPENCLAW_PODMAN_CONTAINER")
        or merged.get("OPENCLAW_CONTAINER")
        or DEFAULTS["OPENCLAW_CONTAINER"]
    )
    config_dir = expand_path(merged["OPENCLAW_CONFIG_DIR"], base_dir)
    workspace_dir = expand_path(merged["OPENCLAW_WORKSPACE_DIR"], base_dir)
    gateway_token = state_env.get("OPENCLAW_GATEWAY_TOKEN") or raw_env.get("OPENCLAW_GATEWAY_TOKEN", "")
    return Config(
        env_file=env_file,
        container_name=container_name,
        image=merged["OPENCLAW_PODMAN_IMAGE"] or merged["OPENCLAW_IMAGE"],
        gateway_port=int(merged["OPENCLAW_PODMAN_GATEWAY_HOST_PORT"]),
        bridge_port=int(merged["OPENCLAW_PODMAN_BRIDGE_HOST_PORT"]),
        board_port=int(merged["OPENCLAW_PODMAN_BOARD_HOST_PORT"]),
        publish_host=merged["OPENCLAW_PODMAN_PUBLISH_HOST"],
        network=merged["OPENCLAW_PODMAN_NETWORK"],
        gateway_bind=merged["OPENCLAW_GATEWAY_BIND"],
        userns=merged["OPENCLAW_PODMAN_USERNS"],
        config_dir=config_dir,
        workspace_dir=workspace_dir,
        gateway_token=gateway_token,
        ollama_base_url=merged["OPENCLAW_OLLAMA_BASE_URL"],
        ollama_model=merged["OPENCLAW_OLLAMA_MODEL"],
        board_image=merged["OPENCLAW_BOARD_IMAGE"],
        raw_env=merged,
    )


def load_config(env_file: Path) -> Config:
    raw_env = parse_env_file(env_file)
    return load_config_from_values(env_file, raw_env)


def load_mattermost_config(env_file: Path) -> MattermostConfig:
    raw_env = parse_env_file(env_file)
    merged = {**DEFAULTS, **raw_env}
    root_dir = mattermost_root_dir(merged, env_file)
    return MattermostConfig(
        env_file=env_file,
        root_dir=root_dir,
        pod_name=f'{merged.get("OPENCLAW_MATTERMOST_CONTAINER", DEFAULT_MATTERMOST_CONTAINER_NAME)}-pod',
        container_name=merged.get("OPENCLAW_MATTERMOST_CONTAINER", DEFAULT_MATTERMOST_CONTAINER_NAME),
        image=merged["OPENCLAW_MATTERMOST_IMAGE"],
        host_port=int(merged["OPENCLAW_MATTERMOST_HOST_PORT"]),
        publish_host=merged["OPENCLAW_MATTERMOST_PUBLISH_HOST"],
        network=merged["OPENCLAW_PODMAN_NETWORK"],
        base_url=merged["OPENCLAW_MATTERMOST_BASE_URL"],
        raw_env=merged,
    )


def mattermost_state_values(env_file: Path) -> dict[str, str]:
    root_dir = mattermost_root_dir(parse_env_file(env_file), env_file)
    return parse_env_file(mattermost_state_env_file(root_dir))


def instance_override_env_key(base_key: str, instance_id: int) -> str:
    return f"{base_key}_INSTANCE_{instance_id:03d}"


def normalize_minute_interval(value: str, fallback: str = "6m") -> str:
    candidate = str(value).strip().lower()
    match = re.fullmatch(r"(\d+)m", candidate)
    if not match:
        return fallback
    return f"{max(1, int(match.group(1)))}m"


def default_mattermost_autonomy_interval_for_instance(base_interval_minutes: int, instance_id: int) -> str:
    offset = MATTERMOST_AUTONOMY_INTERVAL_OFFSETS.get(instance_id, 0)
    return f"{max(1, base_interval_minutes + offset)}m"


def seed_mattermost_autonomy_interval_overrides(env_file: Path, base_interval_minutes: int) -> dict[int, str]:
    env_values = parse_env_file(env_file)
    seeded: dict[int, str] = {}
    for instance_id in sorted(MATTERMOST_AUTONOMY_INTERVAL_OFFSETS):
        key = instance_override_env_key("OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL", instance_id)
        current = env_values.get(key, "").strip()
        if current:
            seeded[instance_id] = normalize_minute_interval(current)
            continue
        interval = default_mattermost_autonomy_interval_for_instance(base_interval_minutes, instance_id)
        write_or_update_env_value(env_file, key, interval)
        seeded[instance_id] = interval
    return seeded


def apply_instance_model_overrides(raw_env: dict[str, str], instance_id: int) -> dict[str, str]:
    overrides = dict(raw_env)
    model_override = overrides.get(instance_override_env_key("OPENCLAW_MODEL_REF", instance_id), "").strip()
    autonomy_override = overrides.get(
        instance_override_env_key("OPENCLAW_MATTERMOST_AUTONOMY_MODEL", instance_id),
        "",
    ).strip()
    autonomy_interval_override = overrides.get(
        instance_override_env_key("OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL", instance_id),
        "",
    ).strip()
    gemini_key_override = overrides.get(instance_override_env_key("GEMINI_API_KEY", instance_id), "").strip()
    google_key_override = overrides.get(instance_override_env_key("GOOGLE_API_KEY", instance_id), "").strip()
    if model_override:
        overrides["OPENCLAW_MODEL_REF"] = model_override
    if autonomy_override:
        overrides["OPENCLAW_MATTERMOST_AUTONOMY_MODEL"] = autonomy_override
    elif model_override:
        overrides["OPENCLAW_MATTERMOST_AUTONOMY_MODEL"] = model_override
    if autonomy_interval_override:
        overrides["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL"] = normalize_minute_interval(autonomy_interval_override)
    if gemini_key_override:
        overrides["GEMINI_API_KEY"] = gemini_key_override
    elif google_key_override:
        overrides["GEMINI_API_KEY"] = google_key_override
    if google_key_override:
        overrides["GOOGLE_API_KEY"] = google_key_override
    return overrides


def apply_mattermost_instance_overrides(raw_env: dict[str, str], env_file: Path, instance_id: int) -> dict[str, str]:
    overrides = apply_instance_model_overrides(raw_env, instance_id)
    state_values = mattermost_state_values(env_file)
    token_key = mattermost_token_key_for_instance(instance_id)
    token = state_values.get(token_key)
    if token:
        overrides["OPENCLAW_MATTERMOST_ENABLED"] = "true"
        overrides["OPENCLAW_MATTERMOST_BOT_TOKEN"] = token
    return overrides


def resolved_instance_model_ref(env_file: Path, instance_id: int) -> str:
    raw_env = parse_env_file(env_file)
    merged = {**DEFAULTS, **raw_env}
    overrides = apply_instance_model_overrides(merged, instance_id)
    return resolved_model_ref(overrides)


def ensure_openclaw_config(cfg: Config) -> None:
    config_path = cfg.config_dir / "openclaw.json"
    payload: dict[str, object] = {}
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Existing config is not valid JSON: {config_path} ({exc})") from exc
        if isinstance(existing, dict):
            payload = existing

    origins: list[str] = []
    for origin in (
        f"http://{cfg.publish_host}:{cfg.gateway_port}",
        f"http://127.0.0.1:{cfg.gateway_port}",
        f"http://localhost:{cfg.gateway_port}",
    ):
        if origin not in origins:
            origins.append(origin)

    agents = ensure_object(payload, "agents")
    defaults = ensure_object(agents, "defaults")
    defaults["workspace"] = CONTAINER_WORKSPACE_DIR
    model = ensure_object(defaults, "model")
    primary_model_ref = model_ref_for(cfg)
    provider_id, provider_model_id = split_model_ref(primary_model_ref)
    model["primary"] = primary_model_ref
    fallbacks_value = cfg.raw_env.get("OPENCLAW_MODEL_FALLBACKS", "").strip()
    if fallbacks_value:
        model["fallbacks"] = [item.strip() for item in fallbacks_value.split(",") if item.strip()]
    elif provider_id == "zai" and provider_model_id == "glm-5.1":
        model["fallbacks"] = ["zai/glm-4.7"]
    else:
        model.pop("fallbacks", None)
    sandbox = ensure_object(defaults, "sandbox")
    sandbox["mode"] = "off"
    default_heartbeat = ensure_object(defaults, "heartbeat")
    default_heartbeat["every"] = "0m"
    default_heartbeat["target"] = "none"
    default_heartbeat["prompt"] = DEFAULT_HEARTBEAT_PROMPT

    agent_entries = ensure_list(agents, "list")
    main_agent = ensure_agent_entry(agent_entries, "main")
    defaults_models = ensure_object(defaults, "models")

    gateway = ensure_object(payload, "gateway")
    gateway["mode"] = "local"
    control_ui = ensure_object(gateway, "controlUi")
    existing_origins = control_ui.get("allowedOrigins")
    if isinstance(existing_origins, list):
        for origin in existing_origins:
            if isinstance(origin, str) and origin not in origins:
                origins.append(origin)
    control_ui["allowedOrigins"] = origins

    auth = ensure_object(payload, "auth")
    cooldowns = ensure_object(auth, "cooldowns")
    try:
        cooldowns["rateLimitedProfileRotations"] = max(
            1, int(cfg.raw_env.get("OPENCLAW_AUTH_RATE_LIMITED_PROFILE_ROTATIONS", "10").strip() or "10")
        )
    except ValueError as exc:
        raise SystemExit("OPENCLAW_AUTH_RATE_LIMITED_PROFILE_ROTATIONS must be an integer.") from exc

    models = ensure_object(payload, "models")
    providers = ensure_object(models, "providers")
    if provider_id == "ollama":
        providers.pop("google", None)
        providers.pop("openrouter", None)
        providers.pop("zai", None)
        ollama = ensure_object(providers, "ollama")
        ollama["api"] = "ollama"
        ollama["baseUrl"] = cfg.ollama_base_url

        existing_models = ollama.get("models")
        preserved_models: list[dict[str, object]] = []
        seen_model_ids: set[str] = {provider_model_id}
        if isinstance(existing_models, list):
            for entry in existing_models:
                if not isinstance(entry, dict):
                    continue
                model_id = entry.get("id")
                if isinstance(model_id, str) and model_id not in seen_model_ids:
                    seen_model_ids.add(model_id)
                    preserved_models.append(entry)
        preserved_models.insert(0, model_spec(provider_model_id, provider_id=provider_id))
        ollama["models"] = preserved_models
    elif provider_id == "openrouter":
        providers.pop("google", None)
        providers.pop("ollama", None)
        providers.pop("zai", None)
        openrouter = ensure_object(providers, "openrouter")
        openrouter["api"] = "openai-completions"
        openrouter["baseUrl"] = cfg.raw_env.get("OPENCLAW_OPENROUTER_BASE_URL", "").strip() or DEFAULT_OPENROUTER_BASE_URL
        openrouter["apiKey"] = "${OPENROUTER_API_KEY}"

        existing_models = openrouter.get("models")
        preserved_models = []
        seen_model_ids = {provider_model_id}
        if isinstance(existing_models, list):
            for entry in existing_models:
                if not isinstance(entry, dict):
                    continue
                model_id = entry.get("id")
                if isinstance(model_id, str) and model_id not in seen_model_ids:
                    seen_model_ids.add(model_id)
                    preserved_models.append(entry)
        preserved_models.insert(0, model_spec(provider_model_id, provider_id=provider_id))
        openrouter["models"] = preserved_models
    elif provider_id == "google":
        providers.pop("ollama", None)
        providers.pop("openrouter", None)
        providers.pop("zai", None)
        google = ensure_object(providers, "google")
        google["api"] = "google-generative-ai"
        google["baseUrl"] = cfg.raw_env.get("OPENCLAW_GOOGLE_BASE_URL", "").strip() or DEFAULT_GOOGLE_BASE_URL
        google["apiKey"] = "${GEMINI_API_KEY}"

        existing_models = google.get("models")
        preserved_models = []
        seen_model_ids = {provider_model_id}
        if isinstance(existing_models, list):
            for entry in existing_models:
                if not isinstance(entry, dict):
                    continue
                model_id = entry.get("id")
                if isinstance(model_id, str) and model_id not in seen_model_ids:
                    seen_model_ids.add(model_id)
                    preserved_models.append(entry)
        preserved_models.insert(0, model_spec(provider_model_id, provider_id=provider_id))
        google["models"] = preserved_models
    elif provider_id == "zai":
        providers.pop("google", None)
        providers.pop("ollama", None)
        providers.pop("openrouter", None)
        providers.pop("zai", None)
        for model_key in list(defaults_models.keys()):
            if model_key.startswith("zai/"):
                defaults_models.pop(model_key, None)

    state_env = parse_env_file(config_env_file(cfg.config_dir))
    mattermost_token = (
        cfg.raw_env.get("OPENCLAW_MATTERMOST_BOT_TOKEN", "").strip()
        or state_env.get("OPENCLAW_MATTERMOST_BOT_TOKEN", "").strip()
    )
    mattermost_base_url = cfg.raw_env.get("OPENCLAW_MATTERMOST_BASE_URL", "").strip()
    mattermost_enabled = truthy_env(cfg.raw_env.get("OPENCLAW_MATTERMOST_ENABLED")) or bool(mattermost_token)
    if mattermost_autonomy_enabled(cfg, mattermost_enabled):
        heartbeat_config = mattermost_autonomy_heartbeat(cfg)
        main_agent["heartbeat"] = heartbeat_config
        for key in ("model", "lightContext", "isolatedSession"):
            if key in heartbeat_config:
                default_heartbeat[key] = heartbeat_config[key]
    elif isinstance(main_agent, dict):
        main_agent.pop("heartbeat", None)
        for key in ("model", "lightContext", "isolatedSession"):
            default_heartbeat.pop(key, None)
    for entry in agent_entries:
        if isinstance(entry, dict) and entry.get("id") != "main":
            entry.pop("heartbeat", None)
            sync_managed_agent_model(entry, primary_model_ref)
    if not defaults_models:
        defaults.pop("models", None)
    if not providers:
        models.pop("providers", None)
    if not models:
        payload.pop("models", None)
    payload.pop("meta", None)

    if mattermost_enabled and mattermost_token and mattermost_base_url:
        channels = ensure_object(payload, "channels")
        mattermost = ensure_object(channels, "mattermost")
        mattermost["enabled"] = True
        mattermost["botToken"] = mattermost_token
        mattermost["baseUrl"] = mattermost_base_url

        for env_key, config_key in (
            ("OPENCLAW_MATTERMOST_CHATMODE", "chatmode"),
            ("OPENCLAW_MATTERMOST_DM_POLICY", "dmPolicy"),
            ("OPENCLAW_MATTERMOST_GROUP_POLICY", "groupPolicy"),
            ("OPENCLAW_MATTERMOST_REPLY_TO_MODE", "replyToMode"),
        ):
            value = cfg.raw_env.get(env_key, "").strip()
            if value:
                mattermost[config_key] = value

        groups = ensure_object(mattermost, "groups")
        default_group = ensure_object(groups, "*")
        default_group["requireMention"] = truthy_env(cfg.raw_env.get("OPENCLAW_MATTERMOST_REQUIRE_MENTION"))
        network = ensure_object(mattermost, "network")
        network["dangerouslyAllowPrivateNetwork"] = truthy_env(
            cfg.raw_env.get("OPENCLAW_MATTERMOST_DANGEROUSLY_ALLOW_PRIVATE_NETWORK")
        )

    tools = ensure_object(payload, "tools")
    tools["profile"] = "full"
    fs_tools = ensure_object(tools, "fs")
    fs_tools["workspaceOnly"] = False
    exec_tools = ensure_object(tools, "exec")
    apply_patch = ensure_object(exec_tools, "applyPatch")
    apply_patch["workspaceOnly"] = False

    plugins = ensure_object(payload, "plugins")
    entries = ensure_object(plugins, "entries")
    active_provider_entry = ensure_object(entries, provider_id)
    active_provider_entry["enabled"] = True
    for provider_name in ("ollama", "openrouter", "google", "zai"):
        if provider_name == provider_id:
            continue
        entry = entries.get(provider_name)
        if isinstance(entry, dict):
            entry["enabled"] = False
    if mattermost_enabled and mattermost_token and mattermost_base_url:
        mattermost_entry = ensure_object(entries, "mattermost")
        mattermost_entry["enabled"] = True

    config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def ensure_state(cfg: Config) -> Config:
    cfg.config_dir.mkdir(parents=True, exist_ok=True)
    cfg.workspace_dir.mkdir(parents=True, exist_ok=True)

    token = cfg.gateway_token.strip()
    if not token:
        token = secrets.token_urlsafe(24)

    write_or_update_env_value(config_env_file(cfg.config_dir), "OPENCLAW_GATEWAY_TOKEN", token)
    for key, value in secret_env_values(cfg.raw_env).items():
        write_or_update_env_value(config_env_file(cfg.config_dir), key, value)
    remove_env_value(cfg.env_file, "OPENCLAW_GATEWAY_TOKEN")

    ensure_openclaw_config(cfg)
    ensure_kube_manifest(cfg, instance_label="single")

    return load_config_from_values(cfg.env_file, public_env_values(cfg.raw_env))


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def podman_bin() -> str:
    resolved = shutil.which("podman")
    if resolved:
        return resolved

    if os.name == "nt":
        candidate = Path.home() / "AppData" / "Local" / "Programs" / "Podman" / "podman.exe"
        if candidate.exists():
            return str(candidate)

    return "podman"


def podman_available() -> bool:
    binary = podman_bin()
    return shutil.which(binary) is not None or Path(binary).exists()


def ensure_podman_network(name: str) -> None:
    network_name = name.strip()
    if not network_name:
        return

    inspect = subprocess.run(
        [podman_bin(), "network", "inspect", network_name],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    if inspect.returncode == 0:
        return

    create = subprocess.run(
        [podman_bin(), "network", "create", network_name],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    if create.returncode != 0 and "already exists" not in (create.stdout + create.stderr):
        raise SystemExit(
            f"failed to create podman network '{network_name}'\n"
            f"stdout:\n{create.stdout}\n"
            f"stderr:\n{create.stderr}"
        )


def podman_host_path(path: Path) -> str:
    resolved = path.resolve()
    if os.name == "nt":
        drive = resolved.drive.rstrip(":").lower()
        tail = resolved.as_posix().split(":/", 1)
        if drive and len(tail) == 2:
            return f"/mnt/{drive}/{tail[1]}"
        return resolved.as_posix()
    return str(resolved)


def runtime_env_pairs(cfg: Config) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for key, value in cfg.raw_env.items():
        if not value:
            continue
        if key in RUNTIME_ENV_EXACT:
            pairs.append((key, value))
    return sorted(pairs)


def redact_env_assignment(value: str) -> str:
    if "=" not in value:
        return value
    key, _ = value.split("=", 1)
    if (
        key == "OPENCLAW_GATEWAY_TOKEN"
        or key == "OPENCLAW_MATTERMOST_BOT_TOKEN"
        or key.startswith("OPENCLAW_MATTERMOST_BOT_TOKEN_")
        or key in {MATTERMOST_ADMIN_PASSWORD_KEY, MATTERMOST_OPERATOR_PASSWORD_KEY}
        or key.endswith("_API_KEY")
        or any(marker in key for marker in SECRET_ENV_CONTAINS)
        or any(marker in key for marker in SECRET_ENV_INSTANCE_MARKERS)
    ):
        return f"{key}=<redacted>"
    return value


def command_for_display(command: list[str]) -> str:
    display: list[str] = []
    redact_next_env = False
    for token in command:
        if redact_next_env:
            display.append(redact_env_assignment(token))
            redact_next_env = False
            continue
        display.append(token)
        if token == "-e":
            redact_next_env = True
    return " ".join(display)


def selected_instance_ids(instance: int | None, count: int | None) -> list[int]:
    if instance is not None and count is not None:
        raise SystemExit("Use either --instance or --count, not both.")
    if instance is not None:
        if instance < 1:
            raise SystemExit("--instance must be 1 or greater.")
        return [instance]
    if count is not None:
        if count < 1:
            raise SystemExit("--count must be 1 or greater.")
        return list(range(1, count + 1))
    return []


def scale_instance_root(raw_env: dict[str, str], env_file: Path) -> Path:
    root_value = raw_env.get("OPENCLAW_SCALE_INSTANCE_ROOT", DEFAULT_SCALE_INSTANCE_ROOT)
    return expand_path(root_value, env_file.parent)


def instance_dir_name(instance_id: int) -> str:
    return f"agent_{instance_id:03d}"


def env_lines(raw_env: dict[str, str]) -> list[str]:
    ordered = []
    seen: set[str] = set()
    for key in list(DEFAULTS.keys()) + ["OPENAI_API_KEY"]:
        if key in raw_env:
            ordered.append(f"{key}={raw_env[key]}")
            seen.add(key)
    for key in sorted(raw_env):
        if key not in seen:
            ordered.append(f"{key}={raw_env[key]}")
    return ordered


def write_generated_env_file(path: Path, raw_env: dict[str, str], header: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [header, ""]
    lines.extend(env_lines(raw_env))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def is_secret_env_key(key: str) -> bool:
    return (
        key in SECRET_ENV_EXACT
        or key.endswith(SECRET_ENV_SUFFIXES)
        or any(marker in key for marker in SECRET_ENV_CONTAINS)
        or any(marker in key for marker in SECRET_ENV_INSTANCE_MARKERS)
    )


def secret_env_values(raw_env: dict[str, str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, value in raw_env.items():
        if value and is_secret_env_key(key):
            values[key] = value
    return values


def public_env_values(raw_env: dict[str, str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, value in raw_env.items():
        if not value:
            values[key] = value
            continue
        if is_secret_env_key(key):
            continue
        values[key] = value
    return values


def scaled_instance(env_file: Path, instance_id: int) -> ScaledInstance:
    base_env = parse_env_file(env_file)
    merged = {**DEFAULTS, **base_env}
    instance_root = scale_instance_root(merged, env_file) / instance_dir_name(instance_id)
    container_base = merged.get("OPENCLAW_PODMAN_CONTAINER") or merged.get("OPENCLAW_CONTAINER") or "openclaw"
    gateway_start = int(merged["OPENCLAW_SCALE_GATEWAY_PORT_START"])
    bridge_start = int(merged["OPENCLAW_SCALE_BRIDGE_PORT_START"])
    board_start = int(merged["OPENCLAW_SCALE_BOARD_PORT_START"])
    port_step = int(merged["OPENCLAW_SCALE_PORT_STEP"])

    raw_env = dict(base_env)
    raw_env["OPENCLAW_CONTAINER"] = f"{container_base}-{instance_id}"
    raw_env["OPENCLAW_PODMAN_CONTAINER"] = f"{container_base}-{instance_id}"
    raw_env["OPENCLAW_PODMAN_GATEWAY_HOST_PORT"] = str(gateway_start + (instance_id - 1) * port_step)
    raw_env["OPENCLAW_PODMAN_BRIDGE_HOST_PORT"] = str(bridge_start + (instance_id - 1) * port_step)
    raw_env["OPENCLAW_PODMAN_BOARD_HOST_PORT"] = str(board_start + (instance_id - 1) * port_step)
    raw_env["OPENCLAW_CONFIG_DIR"] = "."
    raw_env["OPENCLAW_WORKSPACE_DIR"] = "./workspace"
    raw_env = apply_mattermost_instance_overrides(raw_env, env_file, instance_id)

    instance_env_file = instance_root / "control.env"
    cfg = load_config_from_values(instance_env_file, raw_env)
    pod_name = f"{cfg.container_name}-pod"
    return ScaledInstance(
        instance_id=instance_id,
        pod_name=pod_name,
        container_name=cfg.container_name,
        config=cfg,
    )


def ensure_scaled_instance_state(instance: ScaledInstance) -> ScaledInstance:
    cfg = ensure_state(instance.config)
    write_generated_env_file(
        instance.config.env_file,
        public_env_values(instance.config.raw_env),
        f"# Generated for scaled instance {instance.instance_id}.",
    )
    ensure_kube_manifest(cfg, pod_name=instance.pod_name, instance_label=str(instance.instance_id))
    resolved = ScaledInstance(
        instance_id=instance.instance_id,
        pod_name=instance.pod_name,
        container_name=instance.container_name,
        config=cfg,
    )
    scaffold_workspace_files(resolved)
    scaffold_mattermost_tools(resolved)
    return resolved


def print_scaled_instance_summary(instance: ScaledInstance) -> None:
    cfg = instance.config
    print(f"[instance {instance.instance_id}] pod={instance.pod_name} container={instance.container_name}")
    print(f"  gateway=http://{cfg.publish_host}:{cfg.gateway_port}/ bridge={cfg.publish_host}:{cfg.bridge_port}")
    print(f"  state={cfg.config_dir}")
    print(f"  mattermost-tools={mattermost_tools_root(instance)}")


def has_scaled_selection(args: argparse.Namespace) -> bool:
    return getattr(args, "instance", None) is not None or getattr(args, "count", None) is not None


def pod_name_for_config(cfg: Config) -> str:
    return f"{cfg.container_name}-pod"


def board_pod_name_for_config(cfg: Config) -> str:
    return f"{board_container_name(cfg.container_name)}-pod"


def manifest_path_for_config(cfg: Config) -> Path:
    return cfg.config_dir / "pod.yaml"


def board_manifest_path_for_config(cfg: Config) -> Path:
    return cfg.config_dir / "board-pod.yaml"


def shared_board_root_for_config(cfg: Config, instance_label: str) -> Path | None:
    if instance_label == "single":
        return None
    return cfg.config_dir.parent / "shared-board"


def board_service_enabled(instance_label: str) -> bool:
    return instance_label != "single"


def board_container_name(container_name: str) -> str:
    return f"{container_name}-board"


def board_url_for_config(cfg: Config) -> str:
    return f"http://{cfg.publish_host}:{cfg.board_port}/"


def shared_board_mounts(cfg: Config, instance_label: str) -> tuple[list[dict[str, object]], list[dict[str, object]], Path | None]:
    volume_mounts = [
        {
            "name": "openclaw-state",
            "mountPath": CONTAINER_CONFIG_DIR,
        }
    ]
    volumes = [
        {
            "name": "openclaw-state",
            "hostPath": {
                "path": podman_host_path(cfg.config_dir),
                "type": "DirectoryOrCreate",
            },
        }
    ]
    return volume_mounts, volumes, None


def kube_manifest_for(cfg: Config, pod_name: str, instance_label: str) -> dict[str, object]:
    volume_mounts, volumes, _board_root = shared_board_mounts(cfg, instance_label)
    containers = [
        {
            "name": cfg.container_name,
            "image": cfg.image,
            "ports": [
                {
                    "name": "gateway",
                    "containerPort": 18789,
                    "hostPort": cfg.gateway_port,
                    "hostIP": cfg.publish_host,
                    "protocol": "TCP",
                },
                {
                    "name": "bridge",
                    "containerPort": 18790,
                    "hostPort": cfg.bridge_port,
                    "hostIP": cfg.publish_host,
                    "protocol": "TCP",
                },
            ],
            "env": (
                [{"name": key, "value": value} for key, value in runtime_env_pairs(cfg)]
                + [{"name": "TZ", "value": cfg.raw_env.get("OPENCLAW_TIMEZONE", "Asia/Tokyo")}]
            ),
            "volumeMounts": volume_mounts,
        }
    ]

    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": pod_name,
            "labels": {
                MANAGED_LABEL_KEY: "true",
                INSTANCE_LABEL_KEY: instance_label,
            },
            "annotations": {
                "io.podman.annotations.userns": cfg.userns,
            },
        },
        "spec": {
            "restartPolicy": "Always",
            "containers": containers,
            "volumes": volumes,
        },
    }


def board_kube_manifest_for(cfg: Config, pod_name: str, instance_label: str) -> dict[str, object]:
    volume_mounts, volumes, board_root = shared_board_mounts(cfg, instance_label)
    if board_root is None or not board_service_enabled(instance_label):
        raise SystemExit("Board pod is only available for scaled instances.")

    containers = [
        {
            "name": board_container_name(cfg.container_name),
            "image": cfg.board_image,
            "command": [
                "python",
                f"{CONTAINER_SHARED_BOARD_DIR}/tools/shared_board_service.py",
                "--board-root",
                CONTAINER_SHARED_BOARD_DIR,
                "--db-path",
                CONTAINER_BOARD_DB_PATH,
                "--host",
                "0.0.0.0",
                "--port",
                str(DEFAULT_BOARD_CONTAINER_PORT),
                "--template",
                f"{CONTAINER_SHARED_BOARD_DIR}/tools/shared_board_app.html",
            ],
            "ports": [
                {
                    "name": "shared-board",
                    "containerPort": DEFAULT_BOARD_CONTAINER_PORT,
                    "hostPort": cfg.board_port,
                    "hostIP": cfg.publish_host,
                    "protocol": "TCP",
                }
            ],
            "volumeMounts": volume_mounts,
        }
    ]

    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": pod_name,
            "labels": {
                MANAGED_LABEL_KEY: "true",
                INSTANCE_LABEL_KEY: instance_label,
            },
            "annotations": {
                "io.podman.annotations.userns": cfg.userns,
            },
        },
        "spec": {
            "restartPolicy": "Always",
            "containers": containers,
            "volumes": volumes,
        },
    }


def ensure_kube_manifest(cfg: Config, pod_name: str | None = None, instance_label: str = "single") -> Path:
    resolved_pod_name = pod_name or pod_name_for_config(cfg)
    manifest_path = manifest_path_for_config(cfg)
    manifest_path.write_text(
        json.dumps(kube_manifest_for(cfg, resolved_pod_name, instance_label), indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def ensure_board_kube_manifest(cfg: Config, pod_name: str | None = None, instance_label: str = "single") -> Path | None:
    if not board_service_enabled(instance_label):
        return None
    resolved_pod_name = pod_name or board_pod_name_for_config(cfg)
    manifest_path = board_manifest_path_for_config(cfg)
    manifest_path.write_text(
        json.dumps(board_kube_manifest_for(cfg, resolved_pod_name, instance_label), indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def build_kube_play_command_for_manifest(cfg: Config, manifest_path: Path) -> list[str]:
    command = [podman_bin(), "kube", "play", "--replace", "--no-pod-prefix"]
    if cfg.userns:
        command.extend(["--userns", cfg.userns])
    if cfg.network.strip():
        command.extend(["--network", cfg.network])
    command.append(str(manifest_path))
    return command


def build_kube_play_command(
    cfg: Config,
    pod_name: str | None = None,
    instance_label: str = "single",
    ensure_manifest: bool = True,
) -> list[str]:
    manifest_path = manifest_path_for_config(cfg)
    if ensure_manifest:
        manifest_path = ensure_kube_manifest(cfg, pod_name=pod_name, instance_label=instance_label)
    return build_kube_play_command_for_manifest(cfg, manifest_path)


def build_board_kube_play_command(
    cfg: Config,
    pod_name: str | None = None,
    instance_label: str = "single",
    ensure_manifest: bool = True,
) -> list[str]:
    manifest_path = board_manifest_path_for_config(cfg)
    if ensure_manifest:
        ensured = ensure_board_kube_manifest(cfg, pod_name=pod_name, instance_label=instance_label)
        if ensured is None:
            raise SystemExit("Board pod is only available for scaled instances.")
        manifest_path = ensured
    return build_kube_play_command_for_manifest(cfg, manifest_path)


def build_kube_down_command(cfg: Config) -> list[str]:
    return [podman_bin(), "kube", "down", str(manifest_path_for_config(cfg))]


def build_board_kube_down_command(cfg: Config) -> list[str]:
    return [podman_bin(), "kube", "down", str(board_manifest_path_for_config(cfg))]


def run_process(command: list[str], check: bool = True) -> int:
    completed = subprocess.run(command, check=False)
    if check and completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed.returncode


def write_env_value_if_missing(path: Path, key: str, value: str) -> None:
    current = parse_env_file(path).get(key, "").strip()
    if current:
        return
    write_or_update_env_value(path, key, value)


def generate_mattermost_password(prefix: str) -> str:
    return f"{prefix}-{secrets.token_urlsafe(12)}A1!"


def mattermost_manifest_path(cfg: MattermostConfig) -> Path:
    return cfg.root_dir / "pod.yaml"


def mattermost_host_url(cfg: MattermostConfig) -> str:
    host = cfg.publish_host
    if host in {"0.0.0.0", "", "::"}:
        host = "127.0.0.1"
    return f"http://{host}:{cfg.host_port}"


def mattermost_lounge_root(env_file: Path) -> Path:
    return env_file.resolve().parent / ".openclaw" / "mattermost-lounge"


def mattermost_lounge_state_path(env_file: Path) -> Path:
    return mattermost_lounge_root(env_file) / "state.json"


def mattermost_thread_url(cfg: MattermostConfig, root_post_id: str) -> str:
    team_name = cfg.raw_env.get("OPENCLAW_MATTERMOST_TEAM_NAME", DEFAULT_MATTERMOST_TEAM_NAME)
    return f"{mattermost_host_url(cfg)}/{team_name}/pl/{root_post_id}"


def mattermost_channel_url(cfg: MattermostConfig) -> str:
    team_name = cfg.raw_env.get("OPENCLAW_MATTERMOST_TEAM_NAME", DEFAULT_MATTERMOST_TEAM_NAME)
    channel_name = cfg.raw_env.get("OPENCLAW_MATTERMOST_CHANNEL_NAME", DEFAULT_MATTERMOST_CHANNEL_NAME)
    return f"{mattermost_host_url(cfg)}/{team_name}/channels/{channel_name}"


def mattermost_manifest_for(cfg: MattermostConfig) -> dict[str, object]:
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": cfg.pod_name,
            "labels": {
                MANAGED_LABEL_KEY: "true",
                INSTANCE_LABEL_KEY: "mattermost",
            },
            "annotations": {
                "io.podman.annotations.userns": cfg.raw_env["OPENCLAW_PODMAN_USERNS"],
            },
        },
        "spec": {
            "restartPolicy": "Always",
            "containers": [
                {
                    "name": cfg.container_name,
                    "image": cfg.image,
                    "ports": [
                        {
                            "name": "web",
                            "containerPort": DEFAULT_MATTERMOST_HOST_PORT,
                            "hostPort": cfg.host_port,
                            "hostIP": cfg.publish_host,
                            "protocol": "TCP",
                        }
                    ],
                    "env": [
                        {"name": "MM_SERVICESETTINGS_LISTENADDRESS", "value": ":8065"},
                        {
                            "name": "MM_SERVICESETTINGS_SITEURL",
                            "value": cfg.raw_env.get("OPENCLAW_MATTERMOST_SITE_URL", "").strip() or DEFAULT_MATTERMOST_SITE_URL,
                        },
                        {
                            "name": "MM_SERVICESETTINGS_WEBSOCKETURL",
                            "value": cfg.raw_env.get("OPENCLAW_MATTERMOST_WEBSOCKET_URL", "").strip() or DEFAULT_MATTERMOST_WEBSOCKET_URL,
                        },
                        {
                            "name": "MM_SERVICESETTINGS_ALLOWCORSFROM",
                            "value": cfg.raw_env.get("OPENCLAW_MATTERMOST_ALLOW_CORS_FROM", "").strip() or DEFAULT_MATTERMOST_ALLOW_CORS_FROM,
                        },
                        {"name": "MM_SERVICESETTINGS_ENABLELOCALMODE", "value": "true"},
                        {"name": "MM_SERVICESETTINGS_ENABLEDEVELOPER", "value": "true"},
                        {"name": "MM_SERVICESETTINGS_ENABLEBOTACCOUNTCREATION", "value": "true"},
                        {"name": "MM_SERVICESETTINGS_ENABLEUSERACCESSTOKENS", "value": "true"},
                        {"name": "MM_TEAMSETTINGS_ENABLEOPENSERVER", "value": "true"},
                        {
                            "name": "MM_TEAMSETTINGS_TEAMMATENAMEDISPLAY",
                            "value": cfg.raw_env.get("OPENCLAW_MATTERMOST_TEAMMATE_NAME_DISPLAY", "full_name"),
                        },
                        {"name": "MM_LOGSETTINGS_CONSOLELEVEL", "value": "INFO"},
                        {"name": "TZ", "value": cfg.raw_env.get("OPENCLAW_TIMEZONE", "Asia/Tokyo")},
                    ],
                }
            ],
        },
    }


def ensure_mattermost_state(cfg: MattermostConfig) -> dict[str, str]:
    cfg.root_dir.mkdir(parents=True, exist_ok=True)
    state_path = mattermost_state_env_file(cfg.root_dir)
    state_values = parse_env_file(state_path)
    write_or_update_env_value(state_path, MATTERMOST_ADMIN_USERNAME_KEY, cfg.raw_env["OPENCLAW_MATTERMOST_ADMIN_USERNAME"])
    write_or_update_env_value(state_path, MATTERMOST_OPERATOR_USERNAME_KEY, cfg.raw_env["OPENCLAW_MATTERMOST_OPERATOR_USERNAME"])
    if not state_values.get(MATTERMOST_ADMIN_PASSWORD_KEY):
        write_or_update_env_value(state_path, MATTERMOST_ADMIN_PASSWORD_KEY, generate_mattermost_password("Admin"))
    if not state_values.get(MATTERMOST_OPERATOR_PASSWORD_KEY):
        write_or_update_env_value(state_path, MATTERMOST_OPERATOR_PASSWORD_KEY, generate_mattermost_password("Operator"))

    mattermost_manifest_path(cfg).write_text(
        json.dumps(mattermost_manifest_for(cfg), indent=2) + "\n",
        encoding="utf-8",
    )
    return parse_env_file(state_path)


def build_mattermost_kube_play_command(cfg: MattermostConfig, ensure_manifest: bool = True) -> list[str]:
    manifest_path = mattermost_manifest_path(cfg)
    if ensure_manifest:
        ensure_mattermost_state(cfg)
    command = [podman_bin(), "kube", "play", "--replace", "--no-pod-prefix"]
    userns = cfg.raw_env.get("OPENCLAW_PODMAN_USERNS", "").strip()
    if userns:
        command.extend(["--userns", userns])
    if cfg.network.strip():
        command.extend(["--network", cfg.network])
    command.append(str(manifest_path))
    return command


def build_mattermost_kube_down_command(cfg: MattermostConfig) -> list[str]:
    return [podman_bin(), "kube", "down", str(mattermost_manifest_path(cfg))]


def mattermost_exec(cfg: MattermostConfig, args: list[str], timeout_seconds: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [podman_bin(), "exec", cfg.container_name, *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout_seconds,
    )


def mattermost_mmctl(
    cfg: MattermostConfig,
    args: list[str],
    timeout_seconds: int = 120,
    json_output: bool = False,
    allowed_errors: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    command = [MATTERMOST_MMCTL_BIN, "--local"]
    if json_output:
        command.append("--json")
    command.extend(args)
    completed = mattermost_exec(cfg, command, timeout_seconds=timeout_seconds)
    combined = (completed.stdout + completed.stderr).lower()
    if completed.returncode != 0 and not any(token.lower() in combined for token in allowed_errors):
        raise SystemExit(
            f"mattermost mmctl command failed\n"
            f"command: {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def mattermost_mmctl_json(
    cfg: MattermostConfig,
    args: list[str],
    timeout_seconds: int = 120,
    allowed_errors: tuple[str, ...] = (),
) -> dict[str, object] | list[object]:
    completed = mattermost_mmctl(
        cfg,
        args,
        timeout_seconds=timeout_seconds,
        json_output=True,
        allowed_errors=allowed_errors,
    )
    if completed.returncode != 0:
        return {}
    raw = completed.stdout.strip() or completed.stderr.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"mattermost mmctl command returned non-JSON\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        ) from exc


def ensure_mattermost_admin_session(cfg: MattermostConfig, username: str, password: str) -> None:
    script = (
        "rm -f /tmp/openclaw-mmctl-config; "
        "pw=$(mktemp); "
        "trap 'rm -f \"$pw\"' EXIT; "
        "cat > \"$pw\"; "
        f"{MATTERMOST_MMCTL_BIN} --config /tmp/openclaw-mmctl-config auth login http://127.0.0.1:{DEFAULT_MATTERMOST_HOST_PORT} "
        f"--name openclaw --username {shlex.quote(username)} --password-file \"$pw\" >/dev/null"
    )
    completed = subprocess.run(
        [podman_bin(), "exec", "-i", cfg.container_name, "sh", "-lc", script],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        input=password,
        timeout=120,
    )
    if completed.returncode != 0:
        raise SystemExit(
            "failed to authenticate mmctl against Mattermost\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def mattermost_remote_mmctl(
    cfg: MattermostConfig,
    args: list[str],
    timeout_seconds: int = 120,
    json_output: bool = False,
    allowed_errors: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    command = [MATTERMOST_MMCTL_BIN, "--config", "/tmp/openclaw-mmctl-config"]
    if json_output:
        command.append("--json")
    command.extend(args)
    completed = mattermost_exec(cfg, command, timeout_seconds=timeout_seconds)
    combined = (completed.stdout + completed.stderr).lower()
    if completed.returncode != 0 and not any(token.lower() in combined for token in allowed_errors):
        raise SystemExit(
            f"mattermost authenticated mmctl command failed\n"
            f"command: {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def mattermost_remote_mmctl_json(
    cfg: MattermostConfig,
    args: list[str],
    timeout_seconds: int = 120,
    allowed_errors: tuple[str, ...] = (),
) -> dict[str, object] | list[object]:
    completed = mattermost_remote_mmctl(
        cfg,
        args,
        timeout_seconds=timeout_seconds,
        json_output=True,
        allowed_errors=allowed_errors,
    )
    if completed.returncode != 0:
        return {}
    raw = completed.stdout.strip() or completed.stderr.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"mattermost authenticated mmctl command returned non-JSON\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        ) from exc


def wait_for_mattermost_ready(cfg: MattermostConfig, timeout_seconds: int = 180) -> None:
    deadline = time.time() + timeout_seconds
    url = f"{mattermost_host_url(cfg)}/api/v4/system/ping"
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib_request.urlopen(url, timeout=10) as response:
                if response.status == 200:
                    return
        except (urllib_error.URLError, OSError, ConnectionError) as exc:
            last_error = str(exc)
        except Exception as exc:
            last_error = str(exc)
        time.sleep(2)
    raise SystemExit(f"Mattermost did not become ready within {timeout_seconds}s ({last_error})")


def mattermost_http_request(
    cfg: MattermostConfig,
    path: str,
    method: str = "GET",
    token: str | None = None,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    accept: str = "application/json",
) -> tuple[int, dict[str, str], bytes]:
    request_headers: dict[str, str] = {}
    if accept:
        request_headers["Accept"] = accept
    if headers:
        request_headers.update(headers)
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    request = urllib_request.Request(
        f"{mattermost_host_url(cfg)}{path}",
        data=body,
        method=method,
        headers=request_headers,
    )
    with urllib_request.urlopen(request, timeout=30) as response:
        return response.status, dict(response.headers.items()), response.read()


def mattermost_api_request(
    cfg: MattermostConfig,
    path: str,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, str], object | None]:
    body: bytes | None = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    status, response_headers, raw_body = mattermost_http_request(
        cfg,
        path,
        method=method,
        token=token,
        body=body,
        headers=headers,
    )
    parsed: object | None = None
    if raw_body:
        parsed = json.loads(raw_body.decode("utf-8"))
    return status, response_headers, parsed


def mattermost_login(cfg: MattermostConfig, username: str, password: str) -> str:
    status, headers, _ = mattermost_api_request(
        cfg,
        "/api/v4/users/login",
        method="POST",
        payload={"login_id": username, "password": password},
    )
    token = headers.get("Token", "") or headers.get("token", "")
    if status != 200 or not token:
        raise SystemExit("Mattermost login did not return a session token.")
    return token


def mattermost_user_id(cfg: MattermostConfig, username: str, token: str) -> str:
    try:
        _, _, payload = mattermost_api_request(cfg, f"/api/v4/users/username/{username}", token=token)
    except urllib_error.HTTPError as exc:
        if exc.code == 404:
            return ""
        raise
    return str((payload or {}).get("id", "")).strip()


def mattermost_upload_user_image(cfg: MattermostConfig, user_id: str, image_path: Path, token: str) -> None:
    if not image_path.exists():
        raise SystemExit(f"Mattermost bot icon asset is missing: {image_path}")

    boundary = f"----OpenClawMattermost{secrets.token_hex(12)}"
    mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode("ascii"),
            f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n'.encode("utf-8"),
            f"Content-Type: {mime_type}\r\n\r\n".encode("ascii"),
            image_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    mattermost_http_request(
        cfg,
        f"/api/v4/users/{user_id}/image",
        method="POST",
        token=token,
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )


def mattermost_verify_user_image(cfg: MattermostConfig, user_id: str, token: str) -> tuple[str, int]:
    status, headers, raw_body = mattermost_http_request(
        cfg,
        f"/api/v4/users/{user_id}/image",
        token=token,
        accept="image/*",
    )
    content_type = headers.get("Content-Type", "")
    if status != 200 or not content_type.startswith("image/") or not raw_body:
        raise SystemExit(f"Mattermost avatar verification failed for user {user_id}.")
    return content_type, len(raw_body)


def mattermost_persona_username(instance_id: int) -> str:
    mapping = {
        1: "iori",
        2: "tsumugi",
        3: "saku",
    }
    return mapping.get(instance_id, persona_for_instance(instance_id).slug)


def mattermost_persona_display_name(env_file: Path, instance_id: int) -> str:
    profile = persona_for_instance(instance_id)
    _, model_id = split_model_ref(resolved_instance_model_ref(env_file, instance_id))
    return f"{profile.display_name} ｜ {profile.title} ｜ {model_id}"


def mattermost_persona_avatar_file(instance_id: int) -> Path:
    filename = MATTERMOST_ICON_FILENAMES.get(
        instance_id,
        f"{mattermost_persona_username(instance_id)}.png",
    )
    path = MATTERMOST_ICON_ASSET_DIR / filename
    if path.exists():
        return path
    for fallback_name in ("iori.png", "tsumugi.png", "saku.png"):
        fallback = MATTERMOST_ICON_ASSET_DIR / fallback_name
        if fallback.exists():
            return fallback
    raise SystemExit(f"Missing Mattermost avatar asset for instance {instance_id}: {path}")


def load_mattermost_lounge_state(env_file: Path) -> dict[str, object]:
    path = mattermost_lounge_state_path(env_file)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Mattermost lounge state is not valid JSON: {path} ({exc})") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Mattermost lounge state is not a JSON object: {path}")
    return payload


def recent_mattermost_thread_messages(cfg: MattermostConfig, token: str, root_post_id: str, limit: int = 6) -> list[dict[str, object]]:
    _, _, payload = mattermost_api_request(
        cfg,
        f"/api/v4/posts/{root_post_id}/thread?perPage=200",
        token=token,
    )
    if not isinstance(payload, dict):
        return []
    posts = payload.get("posts")
    order = payload.get("order")
    if not isinstance(posts, dict) or not isinstance(order, list):
        return []
    result: list[dict[str, object]] = []
    for post_id in order[-limit:]:
        post = posts.get(post_id)
        if isinstance(post, dict):
            result.append(post)
    return result


def mattermost_channel_id(cfg: MattermostConfig, token: str) -> str:
    team_name = cfg.raw_env.get("OPENCLAW_MATTERMOST_TEAM_NAME", DEFAULT_MATTERMOST_TEAM_NAME)
    channel_name = cfg.raw_env.get("OPENCLAW_MATTERMOST_CHANNEL_NAME", DEFAULT_MATTERMOST_CHANNEL_NAME)
    _, _, team_payload = mattermost_api_request(cfg, f"/api/v4/teams/name/{team_name}", token=token)
    team_id = str((team_payload or {}).get("id", "")).strip()
    if not team_id:
        raise SystemExit(f"Could not resolve Mattermost team: {team_name}")
    _, _, channel_payload = mattermost_api_request(cfg, f"/api/v4/teams/{team_id}/channels/name/{channel_name}", token=token)
    channel_id = str((channel_payload or {}).get("id", "")).strip()
    if not channel_id:
        raise SystemExit(f"Could not resolve Mattermost channel: {team_name}:{channel_name}")
    return channel_id


def mattermost_update_team_metadata(
    cfg: MattermostConfig,
    team_id: str,
    token: str,
    *,
    display_name: str,
    description: str,
) -> None:
    mattermost_api_request(
        cfg,
        f"/api/v4/teams/{team_id}/patch",
        method="PUT",
        token=token,
        payload={
            "display_name": display_name,
            "description": description,
        },
    )


def mattermost_update_channel_metadata(
    cfg: MattermostConfig,
    channel_id: str,
    token: str,
    *,
    display_name: str,
    purpose: str,
    header: str,
) -> None:
    mattermost_api_request(
        cfg,
        f"/api/v4/channels/{channel_id}/patch",
        method="PUT",
        token=token,
        payload={
            "display_name": display_name,
            "purpose": purpose,
            "header": header,
        },
    )


def recent_mattermost_channel_posts(cfg: MattermostConfig, token: str, channel_id: str, limit: int = 8) -> list[dict[str, object]]:
    _, _, payload = mattermost_api_request(
        cfg,
        f"/api/v4/channels/{channel_id}/posts?page=0&per_page=100",
        token=token,
    )
    if not isinstance(payload, dict):
        return []
    posts = payload.get("posts")
    order = payload.get("order")
    if not isinstance(posts, dict) or not isinstance(order, list):
        return []
    result: list[dict[str, object]] = []
    for post_id in reversed(order[-limit:]):
        post = posts.get(post_id)
        if isinstance(post, dict):
            result.append(post)
    return result


def cmd_mattermost_init(args: argparse.Namespace) -> int:
    ensure_env_file(args.env_file)
    cfg = load_mattermost_config(args.env_file)
    ensure_mattermost_state(cfg)
    for key, value in (
        ("OPENCLAW_PODMAN_NETWORK", DEFAULT_PODMAN_NETWORK),
        ("OPENCLAW_MATTERMOST_ENABLED", "true"),
        ("OPENCLAW_MATTERMOST_BASE_URL", DEFAULT_MATTERMOST_BASE_URL),
        ("OPENCLAW_MATTERMOST_CHATMODE", "oncall"),
        ("OPENCLAW_MATTERMOST_DM_POLICY", "open"),
        ("OPENCLAW_MATTERMOST_GROUP_POLICY", "open"),
        ("OPENCLAW_MATTERMOST_REPLY_TO_MODE", "all"),
        ("OPENCLAW_MATTERMOST_REQUIRE_MENTION", "true"),
        ("OPENCLAW_MATTERMOST_DANGEROUSLY_ALLOW_PRIVATE_NETWORK", "true"),
        ("OPENCLAW_MATTERMOST_TEAMMATE_NAME_DISPLAY", "full_name"),
        ("OPENCLAW_MATTERMOST_TEAM_DISPLAY_NAME", DEFAULTS["OPENCLAW_MATTERMOST_TEAM_DISPLAY_NAME"]),
        ("OPENCLAW_MATTERMOST_TEAM_DESCRIPTION", DEFAULTS["OPENCLAW_MATTERMOST_TEAM_DESCRIPTION"]),
        ("OPENCLAW_MATTERMOST_CHANNEL_DISPLAY_NAME", DEFAULTS["OPENCLAW_MATTERMOST_CHANNEL_DISPLAY_NAME"]),
        ("OPENCLAW_MATTERMOST_CHANNEL_PURPOSE", DEFAULTS["OPENCLAW_MATTERMOST_CHANNEL_PURPOSE"]),
        ("OPENCLAW_MATTERMOST_CHANNEL_HEADER", DEFAULTS["OPENCLAW_MATTERMOST_CHANNEL_HEADER"]),
    ):
        write_env_value_if_missing(args.env_file, key, value)

    print("[ok] Mattermost environment initialized")
    print_kv("mattermost dir", str(cfg.root_dir))
    print_kv("manifest", str(mattermost_manifest_path(cfg)))
    print_kv("host url", mattermost_host_url(cfg))
    print_kv("gateway base url", cfg.base_url)
    print_kv("network", cfg.network)
    return 0


def cmd_mattermost_launch(args: argparse.Namespace) -> int:
    ensure_env_file(args.env_file)
    cfg = load_mattermost_config(args.env_file)
    ensure_mattermost_state(cfg)
    if not podman_available():
        print("[fail] podman is not installed or not on PATH", file=sys.stderr)
        return 1
    if not args.dry_run:
        ensure_podman_network(cfg.network)
    command = build_mattermost_kube_play_command(cfg, ensure_manifest=not args.dry_run)
    print(command_for_display(command))
    if args.dry_run:
        return 0
    exit_code = run_process(command, check=False)
    if exit_code == 0:
        wait_for_mattermost_ready(cfg, timeout_seconds=args.timeout)
        print(f"[ok] Mattermost reachable at {mattermost_host_url(cfg)}")
    return exit_code


def cmd_mattermost_status(args: argparse.Namespace) -> int:
    ensure_env_file(args.env_file)
    cfg = load_mattermost_config(args.env_file)
    running = container_running(cfg.container_name)
    marker = "[ok]" if running else "[warn]"
    print(f"{marker} mattermost pod={cfg.pod_name} container={cfg.container_name} running={running}")
    print_kv("host url", mattermost_host_url(cfg))
    print_kv("gateway base url", cfg.base_url)
    print_kv("network", cfg.network)
    print_kv("manifest", str(mattermost_manifest_path(cfg)))
    print_kv("state env", str(mattermost_state_env_file(cfg.root_dir)))
    return 0 if running else 1


def cmd_mattermost_stop(args: argparse.Namespace) -> int:
    ensure_env_file(args.env_file)
    cfg = load_mattermost_config(args.env_file)
    command = build_mattermost_kube_down_command(cfg)
    print(command_for_display(command))
    if args.dry_run:
        return 0
    return run_process(command, check=False)


def cmd_mattermost_seed(args: argparse.Namespace) -> int:
    ensure_env_file(args.env_file)
    cfg = load_mattermost_config(args.env_file)
    state_values = ensure_mattermost_state(cfg)
    if not podman_available():
        print("[fail] podman is not installed or not on PATH", file=sys.stderr)
        return 1
    if not container_running(cfg.container_name):
        raise SystemExit("Mattermost container is not running. Launch it first.")

    wait_for_mattermost_ready(cfg, timeout_seconds=args.timeout)

    admin_username = cfg.raw_env["OPENCLAW_MATTERMOST_ADMIN_USERNAME"]
    admin_email = cfg.raw_env["OPENCLAW_MATTERMOST_ADMIN_EMAIL"]
    operator_username = cfg.raw_env["OPENCLAW_MATTERMOST_OPERATOR_USERNAME"]
    operator_email = cfg.raw_env["OPENCLAW_MATTERMOST_OPERATOR_EMAIL"]
    admin_password = state_values[MATTERMOST_ADMIN_PASSWORD_KEY]
    operator_password = state_values[MATTERMOST_OPERATOR_PASSWORD_KEY]
    team_name = cfg.raw_env["OPENCLAW_MATTERMOST_TEAM_NAME"]
    team_display_name = cfg.raw_env["OPENCLAW_MATTERMOST_TEAM_DISPLAY_NAME"]
    team_description = cfg.raw_env.get("OPENCLAW_MATTERMOST_TEAM_DESCRIPTION", "").strip()
    channel_name = cfg.raw_env["OPENCLAW_MATTERMOST_CHANNEL_NAME"]
    channel_display_name = cfg.raw_env["OPENCLAW_MATTERMOST_CHANNEL_DISPLAY_NAME"]
    channel_purpose = cfg.raw_env.get("OPENCLAW_MATTERMOST_CHANNEL_PURPOSE", "").strip()
    channel_header = cfg.raw_env.get("OPENCLAW_MATTERMOST_CHANNEL_HEADER", "").strip()

    mattermost_mmctl(
        cfg,
        [
            "user",
            "create",
            "--email",
            admin_email,
            "--username",
            admin_username,
            "--password",
            admin_password,
            "--system-admin",
            "--email-verified",
            "--disable-welcome-email",
        ],
        allowed_errors=("already exists",),
    )
    mattermost_mmctl(
        cfg,
        ["user", "change-password", admin_username, "--password", admin_password],
        allowed_errors=("not permitted to use this command",),
    )
    mattermost_mmctl(
        cfg,
        [
            "user",
            "create",
            "--email",
            operator_email,
            "--username",
            operator_username,
            "--password",
            operator_password,
            "--email-verified",
            "--disable-welcome-email",
        ],
        allowed_errors=("already exists",),
    )
    mattermost_mmctl(
        cfg,
        ["user", "change-password", operator_username, "--password", operator_password],
        allowed_errors=("not permitted to use this command",),
    )
    mattermost_mmctl(
        cfg,
        ["team", "create", "--name", team_name, "--display-name", team_display_name],
        allowed_errors=("already exists",),
    )
    mattermost_mmctl(
        cfg,
        ["team", "users", "add", team_name, admin_username, operator_username],
        allowed_errors=("already a member", "is already in the team"),
    )
    mattermost_mmctl(
        cfg,
        [
            "channel",
            "create",
            "--team",
            team_name,
            "--name",
            channel_name,
            "--display-name",
            channel_display_name,
        ],
        allowed_errors=("already exists",),
    )
    mattermost_mmctl(
        cfg,
        [
            "config",
            "set",
            "TeamSettings.TeammateNameDisplay",
            cfg.raw_env.get("OPENCLAW_MATTERMOST_TEAMMATE_NAME_DISPLAY", "full_name"),
        ],
    )
    mattermost_mmctl(
        cfg,
        ["channel", "users", "add", f"{team_name}:{channel_name}", admin_username, operator_username],
        allowed_errors=("already a member", "is already in channel"),
    )
    ensure_mattermost_admin_session(cfg, admin_username, admin_password)
    admin_api_token = mattermost_login(cfg, admin_username, admin_password)
    _, _, team_payload = mattermost_api_request(cfg, f"/api/v4/teams/name/{team_name}", token=admin_api_token)
    team_id = str((team_payload or {}).get("id", "")).strip()
    if not team_id:
        raise SystemExit(f"Could not resolve Mattermost team id for {team_name}.")
    mattermost_update_team_metadata(
        cfg,
        team_id,
        admin_api_token,
        display_name=team_display_name,
        description=team_description,
    )
    channel_id = mattermost_channel_id(cfg, admin_api_token)
    mattermost_update_channel_metadata(
        cfg,
        channel_id,
        admin_api_token,
        display_name=channel_display_name,
        purpose=channel_purpose,
        header=channel_header,
    )

    for instance_id in range(1, args.count + 1):
        token_key = mattermost_token_key_for_instance(instance_id)
        username = mattermost_persona_username(instance_id)
        mattermost_remote_mmctl(
            cfg,
            [
                "bot",
                "create",
                username,
                "--display-name",
                mattermost_persona_display_name(cfg.env_file, instance_id),
                "--description",
                f"OpenClaw agent {instance_id}",
            ],
            allowed_errors=("already exists",),
        )
        mattermost_remote_mmctl(
            cfg,
            [
                "bot",
                "update",
                username,
                "--display-name",
                mattermost_persona_display_name(cfg.env_file, instance_id),
                "--description",
                f"OpenClaw agent {instance_id}",
            ],
        )
        created = mattermost_remote_mmctl_json(
            cfg,
            ["token", "generate", username, f"openclaw-triad-{instance_id:03d}"],
        )
        token = ""
        if isinstance(created, dict):
            token = str(created.get("token", "")).strip()
        elif isinstance(created, list) and created and isinstance(created[0], dict):
            token = str(created[0].get("token", "")).strip()
        if token:
            write_or_update_env_value(mattermost_state_env_file(cfg.root_dir), token_key, token)
            state_values[token_key] = token
        if not state_values.get(token_key):
            raise SystemExit(
                f"Missing bot token for instance {instance_id}. "
                f"If the bot already existed, remove it or provide {token_key} in {mattermost_state_env_file(cfg.root_dir)}."
            )

        user_id = mattermost_user_id(cfg, username, admin_api_token)
        if not user_id:
            raise SystemExit(f"Could not resolve Mattermost bot user id for {username}.")
        avatar_file = mattermost_persona_avatar_file(instance_id)
        mattermost_upload_user_image(cfg, user_id, avatar_file, admin_api_token)
        content_type, image_bytes = mattermost_verify_user_image(cfg, user_id, admin_api_token)

        mattermost_mmctl(
            cfg,
            ["team", "users", "add", team_name, username],
            allowed_errors=("already a member", "is already in the team"),
        )
        mattermost_mmctl(
            cfg,
            ["channel", "users", "add", f"{team_name}:{channel_name}", username],
            allowed_errors=("already a member", "is already in channel"),
        )
        print_kv(f"bot {instance_id}", f"{username} avatar={avatar_file.name} type={content_type} bytes={image_bytes}")

    print("[ok] Mattermost seeded")
    print_kv("team", team_name)
    print_kv("channel", channel_name)
    print_kv("operator", operator_username)
    print_kv("state env", str(mattermost_state_env_file(cfg.root_dir)))
    return 0


def cmd_mattermost_smoke(args: argparse.Namespace) -> int:
    ensure_env_file(args.env_file)
    cfg = load_mattermost_config(args.env_file)
    if not container_running(cfg.container_name):
        raise SystemExit("Mattermost container is not running. Launch it first.")
    wait_for_mattermost_ready(cfg, timeout_seconds=args.timeout)

    state_values = mattermost_state_values(args.env_file)
    operator_username = cfg.raw_env["OPENCLAW_MATTERMOST_OPERATOR_USERNAME"]
    operator_password = state_values.get(MATTERMOST_OPERATOR_PASSWORD_KEY, "")
    if not operator_password:
        raise SystemExit("Operator password is missing. Run mattermost seed first.")

    team_name = cfg.raw_env["OPENCLAW_MATTERMOST_TEAM_NAME"]
    channel_name = cfg.raw_env["OPENCLAW_MATTERMOST_CHANNEL_NAME"]
    token = mattermost_login(cfg, operator_username, operator_password)
    channel_payload = mattermost_mmctl_json(
        cfg,
        ["channel", "search", channel_name, "--team", team_name],
    )
    channel_id = ""
    if isinstance(channel_payload, dict):
        channel_id = str(channel_payload.get("id", ""))
    elif isinstance(channel_payload, list) and channel_payload and isinstance(channel_payload[0], dict):
        channel_id = str(channel_payload[0].get("id", ""))
    if not channel_id:
        raise SystemExit("Could not resolve Mattermost team/channel. Run mattermost seed first.")

    bot_ids: dict[str, str] = {}
    mentions: list[str] = []
    for instance_id in range(1, args.count + 1):
        username = mattermost_persona_username(instance_id)
        mentions.append(f"@{username}")
        _, _, user_payload = mattermost_api_request(cfg, f"/api/v4/users/username/{username}", token=token)
        user_id = str((user_payload or {}).get("id", ""))
        if user_id:
            bot_ids[username] = user_id

    marker = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    prompt = (
        f"{' '.join(mentions)} smoke-test {marker}: "
        "reply in one short sentence with your role and confirm Mattermost is working."
    )
    _, _, post_payload = mattermost_api_request(
        cfg,
        "/api/v4/posts",
        method="POST",
        token=token,
        payload={"channel_id": channel_id, "message": prompt},
    )
    root_post_id = str((post_payload or {}).get("id", ""))
    if not root_post_id:
        raise SystemExit("Mattermost smoke post did not return a post id.")

    deadline = time.time() + args.timeout
    seen_usernames: set[str] = set()
    while time.time() < deadline:
        _, _, posts_payload = mattermost_api_request(
            cfg,
            f"/api/v4/channels/{channel_id}/posts?page=0&per_page=100",
            token=token,
        )
        posts = posts_payload.get("posts", {}) if isinstance(posts_payload, dict) else {}
        for post in posts.values():
            if not isinstance(post, dict):
                continue
            if str(post.get("root_id", "")) != root_post_id:
                continue
            user_id = str(post.get("user_id", ""))
            for username, bot_id in bot_ids.items():
                if user_id == bot_id:
                    seen_usernames.add(username)
        if len(seen_usernames) == len(bot_ids):
            break
        time.sleep(4)

    if len(seen_usernames) != len(bot_ids):
        missing = sorted(set(bot_ids) - seen_usernames)
        raise SystemExit(f"Mattermost smoke timed out waiting for replies from: {', '.join(missing)}")

    print("[ok] Mattermost smoke passed")
    print_kv("channel", f"{team_name}:{channel_name}")
    print_kv("post", root_post_id)
    print_kv("replied", ", ".join(sorted(seen_usernames)))
    return 0


def cmd_mattermost_lounge_enable(args: argparse.Namespace) -> int:
    instance_ids = discussion_instance_ids(args.count)

    ensure_env_file(args.env_file)
    mm_cfg = load_mattermost_config(args.env_file)
    if not podman_available():
        print("[fail] podman is not installed or not on PATH", file=sys.stderr)
        return 1
    if not container_running(mm_cfg.container_name):
        raise SystemExit("Mattermost container is not running. Launch it first.")

    set_mattermost_autonomy_env(args.env_file, enabled=True, interval_minutes=args.interval_minutes)
    instances = reconcile_mattermost_autonomy_instances(
        args.env_file,
        instance_ids,
        remove_legacy_cron=True,
        remove_legacy_autochat=True,
    )
    print("[ok] enabled Mattermost autonomy via heartbeat")
    print_kv("interval", f"{max(1, args.interval_minutes)}m")
    for instance in instances:
        heartbeat = main_agent_heartbeat(instance)
        print(f"[ok] instance {instance.instance_id} heartbeat ready")
        print_kv("config", str(instance.config.config_dir / "openclaw.json"))
        print_kv("heartbeat", json.dumps(heartbeat or {}, ensure_ascii=False))
    return 0


def cmd_mattermost_lounge_status(args: argparse.Namespace) -> int:
    instance_ids = discussion_instance_ids(args.count)

    ensure_env_file(args.env_file)
    mm_cfg = load_mattermost_config(args.env_file)
    overall = 0
    env_values = parse_env_file(args.env_file)
    enabled = truthy_env(env_values.get("OPENCLAW_MATTERMOST_AUTONOMY_ENABLED"))
    print_kv("heartbeat autonomy enabled", "true" if enabled else "false")
    print_kv("heartbeat interval", env_values.get("OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL", "6m"))
    for instance_id in instance_ids:
        instance = ensure_scaled_instance_state(scaled_instance(args.env_file, instance_id))
        running = container_running(instance.container_name)
        marker = "[ok]" if running else "[warn]"
        print(f"{marker} instance {instance_id}: pod={instance.pod_name} container={instance.container_name} running={running}")
        heartbeat = main_agent_heartbeat(instance)
        if heartbeat is None:
            print("  heartbeat: disabled")
            overall = 1
        else:
            print(f"  heartbeat: {json.dumps(heartbeat, ensure_ascii=False)}")
        if running:
            autochat_legacy_job = autochat_job(instance)
            if autochat_legacy_job is not None:
                print(f"  legacy shared-board autochat cron still present: {autochat_legacy_job.get('name')}")
                overall = 1
            legacy_lounge_job = mattermost_lounge_job(instance)
            if legacy_lounge_job is not None:
                print(f"  legacy lounge cron still present: {legacy_lounge_job.get('name')}")
                overall = 1

    print_kv("channel url", mattermost_channel_url(mm_cfg))
    try:
        token = mattermost_login(
            mm_cfg,
            mm_cfg.raw_env["OPENCLAW_MATTERMOST_OPERATOR_USERNAME"],
            mattermost_state_values(args.env_file)[MATTERMOST_OPERATOR_PASSWORD_KEY],
        )
        channel_id = mattermost_channel_id(mm_cfg, token)
        for post in recent_mattermost_channel_posts(mm_cfg, token, channel_id):
            user_id = str(post.get("user_id", ""))
            speaker = user_id
            for instance_id in instance_ids:
                username = mattermost_persona_username(instance_id)
                resolved_user_id = mattermost_user_id(mm_cfg, username, token)
                if user_id == resolved_user_id:
                    speaker = username
                    break
            message = str(post.get("message", "")).replace("\n", " ").strip()
            print(f"  {speaker}: {message[:120]}")
    except Exception as exc:
        print(f"  recent thread fetch failed: {exc}")
        overall = 1
    return overall


def cmd_mattermost_lounge_run_now(args: argparse.Namespace) -> int:
    instance_ids = discussion_instance_ids(args.count)

    ensure_env_file(args.env_file)
    if not truthy_env(parse_env_file(args.env_file).get("OPENCLAW_MATTERMOST_AUTONOMY_ENABLED")):
        raise SystemExit("Mattermost heartbeat autonomy is disabled. Run `mattermost lounge enable` first.")
    for instance_id in instance_ids:
        instance = ensure_scaled_instance_state(scaled_instance(args.env_file, instance_id))
        if not container_running(instance.container_name):
            play_command = build_kube_play_command(
                instance.config,
                pod_name=instance.pod_name,
                instance_label=str(instance.instance_id),
            )
            exit_code = run_process(play_command, check=False)
            if exit_code != 0:
                raise SystemExit(f"Failed to start instance {instance.instance_id} for manual heartbeat wake.")
        output = run_mattermost_lounge_turn_now(instance, timeout_seconds=max(30, args.timeout_ms // 1000))
        print(f"[ok] Mattermost heartbeat wake instance {instance_id}: {console_safe(output)}")

    if args.wait_seconds > 0:
        time.sleep(args.wait_seconds)

    print_kv("channel url", mattermost_channel_url(load_mattermost_config(args.env_file)))
    return 0


def cmd_mattermost_lounge_disable(args: argparse.Namespace) -> int:
    instance_ids = discussion_instance_ids(args.count)

    ensure_env_file(args.env_file)
    set_mattermost_autonomy_env(args.env_file, enabled=False)
    instances = reconcile_mattermost_autonomy_instances(
        args.env_file,
        instance_ids,
        remove_legacy_cron=True,
        remove_legacy_autochat=True,
    )
    print("[ok] disabled Mattermost heartbeat autonomy")
    for instance in instances:
        print(f"[ok] instance {instance.instance_id} heartbeat disabled")
    return 0


def print_kv(title: str, value: str) -> None:
    print(f"{title}: {console_safe(value)}")


def console_safe(value: str) -> str:
    encoding = sys.stdout.encoding or "utf-8"
    return value.encode(encoding, errors="replace").decode(encoding, errors="replace")


def print_model_runtime(cfg: Config) -> None:
    print_kv("model provider", active_model_provider(cfg))
    print_kv("model base url", active_model_base_url(cfg) or "-")
    print_kv("default model", model_ref_for(cfg))


def format_epoch_ms(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    return datetime.fromtimestamp(float(value) / 1000, timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def cmd_init(args: argparse.Namespace) -> int:
    if has_scaled_selection(args):
        ensure_env_file(args.env_file)
        instance_ids = selected_instance_ids(args.instance, args.count)
        for instance_id in instance_ids:
            resolved = ensure_scaled_instance_state(scaled_instance(args.env_file, instance_id))
            print(f"[ok] initialized instance {instance_id}")
            print_scaled_instance_summary(resolved)
        return 0

    ensure_env_file(args.env_file)
    cfg = load_config(args.env_file)
    cfg = ensure_state(cfg)

    print("[ok] Environment initialized")
    print_kv("env file", str(cfg.env_file))
    print_kv("state env", str(config_env_file(cfg.config_dir)))
    print_kv("config dir", str(cfg.config_dir))
    print_kv("workspace dir", str(cfg.workspace_dir))
    print_kv("container", cfg.container_name)
    print_kv("image", cfg.image)
    print_kv("network", cfg.network)
    print_model_runtime(cfg)
    print_kv("tools profile", "full")
    print_kv("sandbox mode", "off")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    checks: list[tuple[str, bool, str]] = []
    blocking_labels = {"podman", ".env", "gateway token"}
    env_exists = args.env_file.exists()
    if env_exists:
        cfg = load_config(args.env_file)
    else:
        cfg = load_config(args.env_file)

    checks.append(("uv", command_exists("uv"), "required to run the helper"))
    checks.append(("podman", podman_available(), "required to launch the container"))
    checks.append(("openclaw", command_exists("openclaw"), "recommended for host-side control plane"))
    model_api_key_name, model_api_key_hint = model_api_key_check(cfg)
    if model_api_key_name:
        checks.append((model_api_key_name, bool(cfg.raw_env.get(model_api_key_name, "").strip()), model_api_key_hint))
    checks.append((".env", env_exists, str(args.env_file)))
    checks.append(("config dir", cfg.config_dir.exists(), str(cfg.config_dir)))
    checks.append(("workspace dir", cfg.workspace_dir.exists(), str(cfg.workspace_dir)))
    checks.append(("gateway token", bool(cfg.gateway_token.strip()), str(config_env_file(cfg.config_dir))))

    exit_code = 0
    for label, passed, detail in checks:
        if passed:
            marker = "[ok]"
        elif label in blocking_labels:
            marker = "[fail]"
        else:
            marker = "[warn]"
        print(f"{marker} {label}: {detail}")
        if label in blocking_labels and not passed:
            exit_code = 1

    print_kv("publish host", cfg.publish_host)
    print_kv("gateway port", str(cfg.gateway_port))
    print_kv("bridge port", str(cfg.bridge_port))
    print_kv("image", cfg.image)
    print_kv("network", cfg.network)
    print_model_runtime(cfg)
    print_kv("tools profile", "full")
    print_kv("sandbox mode", "off")
    return exit_code


def cmd_launch(args: argparse.Namespace) -> int:
    if has_scaled_selection(args):
        ensure_env_file(args.env_file)
        instance_ids = selected_instance_ids(args.instance, args.count)
        if args.dry_run:
            instances = [scaled_instance(args.env_file, instance_id) for instance_id in instance_ids]
        else:
            instances = [ensure_scaled_instance_state(scaled_instance(args.env_file, instance_id)) for instance_id in instance_ids]

        if not args.dry_run and not podman_available():
            print("[fail] podman is not installed or not on PATH", file=sys.stderr)
            return 1
        if not args.dry_run:
            ensure_podman_network(instances[0].config.network)

        overall = 0
        for instance in instances:
            play_command = build_kube_play_command(
                instance.config,
                pod_name=instance.pod_name,
                instance_label=str(instance.instance_id),
                ensure_manifest=not args.dry_run,
            )
            print_scaled_instance_summary(instance)
            print(command_for_display(play_command))

            if args.dry_run:
                continue

            play_exit = run_process(play_command, check=False)
            if play_exit != 0:
                overall = play_exit
            if play_exit == 0:
                print(f"[ok] instance {instance.instance_id} reachable at http://{instance.config.publish_host}:{instance.config.gateway_port}/")
        return overall

    ensure_env_file(args.env_file)
    cfg = load_config(args.env_file)
    if not args.no_init and not args.dry_run:
        cfg = ensure_state(cfg)

    command = build_kube_play_command(cfg, ensure_manifest=not args.dry_run)
    print(command_for_display(command))
    if args.dry_run:
        return 0

    if not podman_available():
        print("[fail] podman is not installed or not on PATH", file=sys.stderr)
        return 1

    ensure_podman_network(cfg.network)
    exit_code = run_process(command, check=False)
    if exit_code == 0:
        print(f"[ok] OpenClaw should be reachable at http://{cfg.publish_host}:{cfg.gateway_port}/")
        print(f"[next] Set OPENCLAW_CONTAINER={cfg.container_name} for host-side CLI usage")
    return exit_code


def cmd_status(args: argparse.Namespace) -> int:
    if has_scaled_selection(args):
        if not podman_available():
            print("[fail] podman is not installed or not on PATH", file=sys.stderr)
            return 1

        overall = 0
        for instance_id in selected_instance_ids(args.instance, args.count):
            instance = scaled_instance(args.env_file, instance_id)
            pod_result = subprocess.run(
                [podman_bin(), "pod", "ps", "--noheading", "--filter", f"name={instance.pod_name}", "--format", "{{.Name}}|{{.Status}}"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            container_result = subprocess.run(
                [podman_bin(), "ps", "-a", "--noheading", "--filter", f"name={instance.container_name}", "--format", "{{.Names}}|{{.Status}}"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            pod_line = pod_result.stdout.strip() or "missing|not-found"
            container_line = container_result.stdout.strip() or "missing|not-found"
            print(f"[instance {instance_id}] pod={pod_line} container={container_line}")
            if "not-found" in pod_line or "not-found" in container_line:
                overall = 1
        return overall

    cfg = load_config(args.env_file)
    if not podman_available():
        print("[fail] podman is not installed or not on PATH", file=sys.stderr)
        return 1
    return run_process(
        [podman_bin(), "pod", "ps", "--filter", f"name={pod_name_for_config(cfg)}"],
        check=False,
    )


def cmd_logs(args: argparse.Namespace) -> int:
    if has_scaled_selection(args):
        if getattr(args, "count", None) is not None:
            raise SystemExit("logs only supports --instance.")
        if not podman_available():
            print("[fail] podman is not installed or not on PATH", file=sys.stderr)
            return 1
        instance = scaled_instance(args.env_file, args.instance)
        command = [podman_bin(), "logs"]
        if args.follow:
            command.append("-f")
        command.append(instance.container_name)
        return run_process(command, check=False)

    cfg = load_config(args.env_file)
    if not podman_available():
        print("[fail] podman is not installed or not on PATH", file=sys.stderr)
        return 1

    command = [podman_bin(), "logs"]
    if args.follow:
        command.append("-f")
    command.append(cfg.container_name)
    return run_process(command, check=False)


def cmd_stop(args: argparse.Namespace) -> int:
    if has_scaled_selection(args):
        if not args.dry_run and not podman_available():
            print("[fail] podman is not installed or not on PATH", file=sys.stderr)
            return 1

        overall = 0
        for instance_id in selected_instance_ids(args.instance, args.count):
            instance = scaled_instance(args.env_file, instance_id)
            down_command = build_kube_down_command(instance.config)
            print(f"[instance {instance_id}] {command_for_display(down_command)}")
            if args.dry_run:
                continue
            down_exit = run_process(down_command, check=False)
            if down_exit != 0:
                overall = down_exit
        return overall

    cfg = load_config(args.env_file)
    if not podman_available():
        print("[fail] podman is not installed or not on PATH", file=sys.stderr)
        return 1

    stop_command = build_kube_down_command(cfg)
    if args.dry_run:
        print(command_for_display(stop_command))
        return 0

    stop_code = run_process(stop_command, check=False)
    return stop_code


def cmd_print_env(args: argparse.Namespace) -> int:
    if has_scaled_selection(args):
        if getattr(args, "count", None) is not None:
            raise SystemExit("print-env only supports --instance.")
        instance = scaled_instance(args.env_file, args.instance)
        cfg = instance.config
        print_kv("instance", str(instance.instance_id))
        print_kv("pod", instance.pod_name)
        print_kv("container", instance.container_name)
        print_kv("env file", str(cfg.env_file))
        print_kv("manifest", str(manifest_path_for_config(cfg)))
        print_kv("image", cfg.image)
        print_kv("publish host", cfg.publish_host)
        print_kv("gateway port", str(cfg.gateway_port))
        print_kv("bridge port", str(cfg.bridge_port))
        print_kv("config dir", str(cfg.config_dir))
        print_kv("workspace dir", str(cfg.workspace_dir))
        print_kv("mattermost tools dir", str(mattermost_tools_root(instance)))
        print_kv("network", cfg.network)
        print_model_runtime(cfg)
        print_kv("tools profile", "full")
        print_kv("sandbox mode", "off")
        return 0

    cfg = load_config(args.env_file)
    print_kv("env file", str(cfg.env_file))
    print_kv("container", cfg.container_name)
    print_kv("image", cfg.image)
    print_kv("publish host", cfg.publish_host)
    print_kv("gateway port", str(cfg.gateway_port))
    print_kv("bridge port", str(cfg.bridge_port))
    print_kv("gateway bind", cfg.gateway_bind)
    print_kv("userns", cfg.userns)
    print_kv("config dir", str(cfg.config_dir))
    print_kv("state env", str(config_env_file(cfg.config_dir)))
    print_kv("manifest", str(manifest_path_for_config(cfg)))
    print_kv("workspace dir", str(cfg.workspace_dir))
    print_kv("network", cfg.network)
    print_model_runtime(cfg)
    print_kv("tools profile", "full")
    print_kv("sandbox mode", "off")
    print_kv("token present", "yes" if bool(cfg.gateway_token.strip()) else "no")
    return 0


def cmd_discuss(args: argparse.Namespace) -> int:
    ensure_env_file(args.env_file)
    if not podman_available():
        print("[fail] podman is not installed or not on PATH", file=sys.stderr)
        return 1

    topic = args.topic.strip()
    if not topic:
        raise SystemExit("--topic must not be empty.")

    instance_ids = discussion_instance_ids(args.count)
    if args.starter not in instance_ids:
        raise SystemExit("--starter must be within the selected discussion instance ids.")

    instances: dict[int, ScaledInstance] = {}
    for instance_id in instance_ids:
        instance = ensure_scaled_instance_state(scaled_instance(args.env_file, instance_id))
        ensure_scaled_instance_running(instance)
        ensure_named_agent(instance, discuss_agent_id(instance.instance_id))
        instances[instance_id] = instance

    starter = instances[args.starter]
    board_root = shared_board_root(starter)
    thread_id = slugify_thread_id(args.thread_id) if args.thread_id else discussion_thread_id(topic)
    thread = discussion_thread(board_root, thread_id)
    if thread.thread_dir.exists() and any(thread.thread_dir.iterdir()):
        raise SystemExit(f"Thread already exists and is not empty: {thread.thread_dir}")
    thread.thread_dir.mkdir(parents=True, exist_ok=True)

    starter_payload = run_pod_local_agent_until_file(
        starter,
        build_discussion_topic_prompt(starter, thread, topic, instance_ids),
        expected_path=thread.topic_path,
        timeout_seconds=args.timeout,
        stage_label="starter topic",
        session_id=f"{thread.thread_id}-topic-{starter.instance_id}",
        agent_id=discuss_agent_id(starter.instance_id),
    )
    ensure_discussion_file(thread.topic_path, "topic")
    print_discussion_agent_result(starter, "posted topic", starter_payload)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    reply_paths: list[Path] = []
    for instance_id in instance_ids:
        if instance_id == args.starter:
            continue
        instance = instances[instance_id]
        reply_path = discussion_reply_path(thread, instance, stamp)
        payload = run_pod_local_agent_until_file(
            instance,
            build_discussion_reply_prompt(instance, thread, reply_path),
            expected_path=reply_path,
            timeout_seconds=args.timeout,
            stage_label=f"reply for instance {instance.instance_id}",
            session_id=f"{thread.thread_id}-reply-{instance.instance_id}",
            agent_id=discuss_agent_id(instance.instance_id),
        )
        ensure_discussion_file(reply_path, "reply")
        reply_paths.append(reply_path)
        print_discussion_agent_result(instance, "posted reply", payload)

    summary_payload = run_pod_local_agent(
        starter,
        build_discussion_summary_prompt(starter, thread, reply_paths),
        timeout_seconds=args.timeout,
        agent_id=discuss_agent_id(starter.instance_id),
        session_id=f"{thread.thread_id}-summary-{starter.instance_id}",
    )
    if not discussion_file_ready(thread.summary_path):
        summary_body = discussion_markdown_body(summary_payload)
        if not summary_body:
            raise SystemExit(f"Summary stage produced no markdown body:\n{json.dumps(summary_payload, ensure_ascii=False, indent=2)}")
        summary_payload = run_pod_local_agent_until_file(
            starter,
            build_exact_write_prompt(container_summary_path(thread), summary_body),
            expected_path=thread.summary_path,
            timeout_seconds=args.timeout,
            stage_label="summary writeback",
            session_id=f"{thread.thread_id}-summary-writeback-{starter.instance_id}",
            agent_id=discuss_agent_id(starter.instance_id),
        )
    ensure_discussion_file(thread.summary_path, "summary")
    print_discussion_agent_result(starter, "posted summary", summary_payload)
    viewer_index = render_board_view(board_root)

    print_kv("thread id", thread.thread_id)
    print_kv("thread dir", str(thread.thread_dir))
    print_kv("topic file", str(thread.topic_path))
    for reply_path in reply_paths:
        print_kv("reply file", str(reply_path))
    print_kv("summary file", str(thread.summary_path))
    print_kv("viewer", str(viewer_index))
    return 0


def cmd_autochat_enable(args: argparse.Namespace) -> int:
    instance_ids = discussion_instance_ids(args.count)
    if instance_ids != [1, 2, 3]:
        raise SystemExit("autochat currently supports exactly 3 instances.")

    ensure_env_file(args.env_file)
    if not podman_available():
        print("[fail] podman is not installed or not on PATH", file=sys.stderr)
        return 1

    for instance_id in instance_ids:
        instance = ensure_scaled_instance_state(scaled_instance(args.env_file, instance_id))
        ensure_scaled_instance_running(instance)
        ensure_autochat_agent(instance)
        job = add_autochat_job(instance, interval_minutes=args.interval_minutes, timeout_seconds=args.timeout)
        print(f"[ok] enabled autochat for instance {instance_id}")
        print_kv("job id", str(job.get("id")))
        print_kv("job name", str(job.get("name")))
        schedule = job.get("schedule") if isinstance(job, dict) else {}
        if isinstance(schedule, dict):
            print_kv("schedule", json.dumps(schedule, ensure_ascii=False))
    print_kv("live thread", str(autochat_thread(shared_board_root(scaled_instance(args.env_file, 1))).thread_dir))
    return 0


def cmd_autochat_status(args: argparse.Namespace) -> int:
    instance_ids = discussion_instance_ids(args.count)
    if instance_ids != [1, 2, 3]:
        raise SystemExit("autochat currently supports exactly 3 instances.")

    ensure_env_file(args.env_file)
    overall = 0
    for instance_id in instance_ids:
        instance = scaled_instance(args.env_file, instance_id)
        running = container_running(instance.container_name)
        marker = "[ok]" if running else "[warn]"
        print(f"{marker} instance {instance_id}: pod={instance.pod_name} container={instance.container_name} running={running}")
        if not running:
            overall = 1
            continue
        job = autochat_job(instance)
        if job is None:
            print("  autochat: missing")
            overall = 1
            continue
        print(f"  autochat: {job.get('name')} enabled={job.get('enabled')}")
        state = job.get("state")
        if isinstance(state, dict):
            print(f"  nextRunAtMs: {state.get('nextRunAtMs')}")
        schedule = job.get("schedule")
        if isinstance(schedule, dict):
            print(f"  schedule: {json.dumps(schedule, ensure_ascii=False)}")
    live_thread = autochat_thread(shared_board_root(scaled_instance(args.env_file, 1))).thread_dir
    if live_thread.exists():
        files = sorted(path.name for path in live_thread.iterdir() if path.is_file())
        print(f"live thread files: {len(files)}")
        for name in files[-6:]:
            print(f"  {name}")
    else:
        print(f"live thread files: missing ({live_thread})")
        overall = 1
    return overall


def cmd_autochat_run_now(args: argparse.Namespace) -> int:
    instance_ids = discussion_instance_ids(args.count)
    if instance_ids != [1, 2, 3]:
        raise SystemExit("autochat currently supports exactly 3 instances.")

    ensure_env_file(args.env_file)
    for instance_id in instance_ids:
        instance = ensure_scaled_instance_state(scaled_instance(args.env_file, instance_id))
        ensure_scaled_instance_running(instance)
        result = run_autochat_job_now(instance, timeout_ms=args.timeout_ms)
        print(f"[ok] enqueued autochat turn for instance {instance_id}: runId={result.get('runId')}")

    if args.wait_seconds > 0:
        time.sleep(args.wait_seconds)

    live_thread = autochat_thread(shared_board_root(scaled_instance(args.env_file, 1))).thread_dir
    if live_thread.exists():
        files = sorted(path.name for path in live_thread.iterdir() if path.is_file())
        print_kv("live thread", str(live_thread))
        print_kv("file count", str(len(files)))
        for name in files[-6:]:
            print(f"  {name}")
    return 0


def cmd_autochat_disable(args: argparse.Namespace) -> int:
    instance_ids = discussion_instance_ids(args.count)
    if instance_ids != [1, 2, 3]:
        raise SystemExit("autochat currently supports exactly 3 instances.")

    ensure_env_file(args.env_file)
    removed_any = False
    for instance_id in instance_ids:
        instance = scaled_instance(args.env_file, instance_id)
        if not container_running(instance.container_name):
            print(f"[warn] instance {instance_id} is not running; skipping cron removal")
            continue
        removed = remove_autochat_job(instance)
        removed_any = removed_any or removed
        print(f"[ok] autochat remove instance {instance_id}: removed={removed}")
    return 0 if removed_any else 1


def cmd_boardview(args: argparse.Namespace) -> int:
    ensure_env_file(args.env_file)
    board_root = shared_board_root(scaled_instance(args.env_file, 1))
    viewer_index = render_board_view(board_root)
    target = viewer_index
    if args.thread:
        thread_page = board_root / "viewer" / "threads" / f"{slugify_thread_id(args.thread)}.html"
        if thread_page.exists():
            target = thread_page
        else:
            raise SystemExit(f"Viewer thread page not found: {thread_page}")
    print_kv("viewer", str(target))
    if args.open:
        if os.name == "nt":
            os.startfile(target)  # type: ignore[attr-defined]
        else:
            raise SystemExit("--open is only supported on Windows hosts.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openclaw-podman",
        description="Starter helper for autonomous OpenClaw teams on Podman.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Path to the env file. Defaults to ./.env",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create .env and seed state directories.")
    init_parser.add_argument("--instance", type=int, help="Initialize one scaled instance by id.")
    init_parser.add_argument("--count", type=int, help="Initialize the first N scaled instances.")
    init_parser.set_defaults(func=cmd_init)

    doctor_parser = subparsers.add_parser("doctor", help="Check prerequisites and current config.")
    doctor_parser.set_defaults(func=cmd_doctor)

    launch_parser = subparsers.add_parser("launch", help="Launch the single instance or one/many scaled instances.")
    launch_parser.add_argument("--dry-run", action="store_true", help="Print the final command only.")
    launch_parser.add_argument("--no-init", action="store_true", help="Skip init/state seeding.")
    launch_parser.add_argument("--instance", type=int, help="Launch one scaled instance by id.")
    launch_parser.add_argument("--count", type=int, help="Launch the first N scaled instances as pods.")
    launch_parser.set_defaults(func=cmd_launch)

    status_parser = subparsers.add_parser("status", help="Show single-instance or scaled-instance status.")
    status_parser.add_argument("--instance", type=int, help="Show one scaled instance by id.")
    status_parser.add_argument("--count", type=int, help="Show the first N scaled instances.")
    status_parser.set_defaults(func=cmd_status)

    logs_parser = subparsers.add_parser("logs", help="Show single-instance or one scaled instance logs.")
    logs_parser.add_argument("-f", "--follow", action="store_true", help="Follow the log output.")
    logs_parser.add_argument("--instance", type=int, help="Show logs for one scaled instance by id.")
    logs_parser.set_defaults(func=cmd_logs)

    stop_parser = subparsers.add_parser("stop", help="Stop the single instance or one/many scaled instances.")
    stop_parser.add_argument("--remove", action="store_true", help="Remove the container after stopping.")
    stop_parser.add_argument("--dry-run", action="store_true", help="Print the stop command only.")
    stop_parser.add_argument("--instance", type=int, help="Stop one scaled instance by id.")
    stop_parser.add_argument("--count", type=int, help="Stop the first N scaled instances.")
    stop_parser.set_defaults(func=cmd_stop)

    print_env_parser = subparsers.add_parser("print-env", help="Print single-instance or one scaled instance env values.")
    print_env_parser.add_argument("--instance", type=int, help="Print env for one scaled instance by id.")
    print_env_parser.set_defaults(func=cmd_print_env)

    mattermost_parser = subparsers.add_parser("mattermost", help="Manage a local Mattermost pod for OpenClaw channel testing.")
    mattermost_subparsers = mattermost_parser.add_subparsers(dest="mattermost_command", required=True)

    mattermost_init_parser = mattermost_subparsers.add_parser("init", help="Prepare local Mattermost state and defaults.")
    mattermost_init_parser.set_defaults(func=cmd_mattermost_init)

    mattermost_launch_parser = mattermost_subparsers.add_parser("launch", help="Launch the local Mattermost pod.")
    mattermost_launch_parser.add_argument("--dry-run", action="store_true", help="Print the launch command only.")
    mattermost_launch_parser.add_argument("--timeout", type=int, default=180, help="Wait this many seconds for readiness (default: 180).")
    mattermost_launch_parser.set_defaults(func=cmd_mattermost_launch)

    mattermost_status_parser = mattermost_subparsers.add_parser("status", help="Show Mattermost pod status.")
    mattermost_status_parser.set_defaults(func=cmd_mattermost_status)

    mattermost_stop_parser = mattermost_subparsers.add_parser("stop", help="Stop the local Mattermost pod.")
    mattermost_stop_parser.add_argument("--dry-run", action="store_true", help="Print the stop command only.")
    mattermost_stop_parser.set_defaults(func=cmd_mattermost_stop)

    mattermost_seed_parser = mattermost_subparsers.add_parser("seed", help="Create users, channel, and Mattermost bot accounts.")
    mattermost_seed_parser.add_argument("--count", type=int, default=3, help="Number of Mattermost bot accounts to seed (default: 3).")
    mattermost_seed_parser.add_argument("--timeout", type=int, default=180, help="Wait this many seconds for Mattermost readiness (default: 180).")
    mattermost_seed_parser.set_defaults(func=cmd_mattermost_seed)

    mattermost_smoke_parser = mattermost_subparsers.add_parser("smoke", help="Post a mention to the Mattermost channel and wait for bot replies.")
    mattermost_smoke_parser.add_argument("--count", type=int, default=3, help="Number of bot replies expected (default: 3).")
    mattermost_smoke_parser.add_argument("--timeout", type=int, default=120, help="Wait this many seconds for replies (default: 120).")
    mattermost_smoke_parser.set_defaults(func=cmd_mattermost_smoke)

    mattermost_lounge_parser = mattermost_subparsers.add_parser("lounge", help="Manage heartbeat-driven autonomous Mattermost chatter.")
    mattermost_lounge_subparsers = mattermost_lounge_parser.add_subparsers(dest="mattermost_lounge_command", required=True)

    mattermost_lounge_enable_parser = mattermost_lounge_subparsers.add_parser("enable", help="Enable heartbeat-driven autonomous chatter for the selected agents.")
    mattermost_lounge_enable_parser.add_argument("--count", type=int, help="Scaled instance count to manage (default: 3).")
    mattermost_lounge_enable_parser.add_argument("--interval-minutes", type=int, default=6, help="Heartbeat interval per agent in minutes (default: 6).")
    mattermost_lounge_enable_parser.add_argument("--timeout", type=int, default=300, help="Compatibility placeholder; config is applied immediately and pods are reloaded (default: 300).")
    mattermost_lounge_enable_parser.set_defaults(func=cmd_mattermost_lounge_enable)

    mattermost_lounge_status_parser = mattermost_lounge_subparsers.add_parser("status", help="Show Mattermost heartbeat autonomy status.")
    mattermost_lounge_status_parser.add_argument("--count", type=int, help="Scaled instance count to inspect (default: 3).")
    mattermost_lounge_status_parser.set_defaults(func=cmd_mattermost_lounge_status)

    mattermost_lounge_run_now_parser = mattermost_lounge_subparsers.add_parser("run-now", help="Trigger one immediate heartbeat wake for each selected agent.")
    mattermost_lounge_run_now_parser.add_argument("--count", type=int, help="Scaled instance count to trigger (default: 3).")
    mattermost_lounge_run_now_parser.add_argument("--timeout-ms", type=int, default=300000, help="Per-turn timeout in ms for direct run-now execution (default: 300000).")
    mattermost_lounge_run_now_parser.add_argument("--wait-seconds", type=int, default=10, help="Wait this many seconds before printing the thread info (default: 10).")
    mattermost_lounge_run_now_parser.set_defaults(func=cmd_mattermost_lounge_run_now)

    mattermost_lounge_disable_parser = mattermost_lounge_subparsers.add_parser("disable", help="Disable heartbeat-driven autonomous chatter and remove legacy lounge cron jobs.")
    mattermost_lounge_disable_parser.add_argument("--count", type=int, help="Scaled instance count to disable (default: 3).")
    mattermost_lounge_disable_parser.set_defaults(func=cmd_mattermost_lounge_disable)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.env_file = Path(args.env_file).resolve()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
