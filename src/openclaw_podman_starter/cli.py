from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = REPO_ROOT / ".env"
ENV_EXAMPLE_FILE = REPO_ROOT / ".env.example"
AUTOCHAT_SCRIPT_FILE = REPO_ROOT / "scripts" / "autochat_turn.py"
BOARD_RENDER_SCRIPT_FILE = REPO_ROOT / "scripts" / "render_board_view.py"
CONTAINER_CONFIG_DIR = "/home/node/.openclaw"
CONTAINER_WORKSPACE_DIR = "/home/node/.openclaw/workspace"
CONTAINER_SHARED_BOARD_DIR = "/home/node/.openclaw/shared-board"
STATE_ENV_NAME = ".env"
DEFAULT_OLLAMA_MODEL_ID = "gemma4:e2b"
DEFAULT_MODEL_REF = f"ollama/{DEFAULT_OLLAMA_MODEL_ID}"
DEFAULT_OLLAMA_BASE_URL = "http://host.containers.internal:11434"
DEFAULT_CONTEXT_WINDOW = 131072
DEFAULT_SCALE_INSTANCE_ROOT = "./.openclaw/instances"
DEFAULT_SCALE_GATEWAY_PORT_START = 18789
DEFAULT_SCALE_BRIDGE_PORT_START = 18790
DEFAULT_SCALE_PORT_STEP = 2
MANAGED_LABEL_KEY = "io.openclaw-podman.managed"
INSTANCE_LABEL_KEY = "io.openclaw-podman.instance"
WORKSPACE_MANAGED_MARKER = "<!-- Managed by openclaw-podman-starter: persona scaffold -->"
BOARD_MANAGED_MARKER = "<!-- Managed by openclaw-podman-starter: shared board scaffold -->"
DEFAULT_DISCUSSION_INSTANCE_COUNT = 3
AUTOCHAT_THREAD_ID = "background-lounge"
AUTOCHAT_JOB_PREFIX = "shared-board-autochat"

DEFAULTS = {
    "OPENCLAW_CONTAINER": "openclaw",
    "OPENCLAW_PODMAN_CONTAINER": "openclaw",
    "OPENCLAW_PODMAN_IMAGE": "",
    "OPENCLAW_IMAGE": "ghcr.io/openclaw/openclaw:2026.4.5",
    "OPENCLAW_PODMAN_GATEWAY_HOST_PORT": "18789",
    "OPENCLAW_PODMAN_BRIDGE_HOST_PORT": "18790",
    "OPENCLAW_PODMAN_PUBLISH_HOST": "127.0.0.1",
    "OPENCLAW_GATEWAY_BIND": "lan",
    "OPENCLAW_PODMAN_USERNS": "keep-id",
    "OPENCLAW_CONFIG_DIR": "./.openclaw",
    "OPENCLAW_WORKSPACE_DIR": "./.openclaw/workspace",
    "OPENCLAW_OLLAMA_BASE_URL": DEFAULT_OLLAMA_BASE_URL,
    "OPENCLAW_OLLAMA_MODEL": DEFAULT_OLLAMA_MODEL_ID,
    "OPENCLAW_SCALE_INSTANCE_ROOT": DEFAULT_SCALE_INSTANCE_ROOT,
    "OPENCLAW_SCALE_GATEWAY_PORT_START": str(DEFAULT_SCALE_GATEWAY_PORT_START),
    "OPENCLAW_SCALE_BRIDGE_PORT_START": str(DEFAULT_SCALE_BRIDGE_PORT_START),
    "OPENCLAW_SCALE_PORT_STEP": str(DEFAULT_SCALE_PORT_STEP),
}

RUNTIME_ENV_EXACT = {
    "OPENCLAW_GATEWAY_BIND",
}

RUNTIME_ENV_SUFFIXES = ("_API_KEY",)


@dataclass
class Config:
    env_file: Path
    container_name: str
    image: str
    gateway_port: int
    bridge_port: int
    publish_host: str
    gateway_bind: str
    userns: str
    config_dir: Path
    workspace_dir: Path
    gateway_token: str
    ollama_base_url: str
    ollama_model: str
    raw_env: dict[str, str]


@dataclass
class ScaledInstance:
    instance_id: int
    pod_name: str
    container_name: str
    config: Config


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
        title="段取り番",
        creature="現場好きのまとめ役",
        vibe="落ち着いてるけどフランク",
        signature="north-star",
        specialty="デプロイ、manifest、設定差分、state の面倒を見る",
        collaboration_style="ふわっとした話を、すぐ動ける段取りにする",
        caution="急に壊すより、まず見てから小さく直す",
        heartbeat_focus="pod の健全性、設定差分、gateway 到達性",
    ),
    2: PersonaProfile(
        instance_id=2,
        slug="lyra",
        display_name="つむぎ",
        title="ひらめき係",
        creature="しゃべるメモ帳",
        vibe="やわらかくてノリがいい",
        signature="silver-comet",
        specialty="試作、docs、prompt、アイデアのたたき台づくり",
        collaboration_style="まず雑に叩き台を出して、一緒に育てる",
        caution="早すぎる決め打ちはしない",
        heartbeat_focus="prompt 品質、docs の鮮度、workspace 引き継ぎメモ",
    ),
    3: PersonaProfile(
        instance_id=3,
        slug="noctis",
        display_name="さく",
        title="検証番",
        creature="夜更かし気味の見張り役",
        vibe="クールだけど話は通じる",
        signature="obsidian-ring",
        specialty="tests、diff、回帰確認、変なところ探し",
        collaboration_style="うのみにせず、一回ひっくり返して確かめる",
        caution="怪しい時は無理に進めず、一回止まる",
        heartbeat_focus="failed run、logs、health check、回帰シグナル",
    ),
}


def normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").strip()


def persona_for_instance(instance_id: int) -> PersonaProfile:
    profile = TRIAD_PERSONAS.get(instance_id)
    if profile:
        return profile

    return PersonaProfile(
        instance_id=instance_id,
        slug=f"shard-{instance_id}",
        display_name=f"端雲{instance_id}",
        title="なんでも係",
        creature="実務寄りの相棒",
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
    for instance_id in sorted(TRIAD_PERSONAS):
        if instance_id == current_instance_id:
            continue
        sibling = TRIAD_PERSONAS[instance_id]
        lines.append(
            f"- Instance {instance_id} / {sibling.display_name}: {sibling.title}。担当は {sibling.specialty}。"
        )
    return "\n".join(lines)


def render_workspace_files(instance: ScaledInstance) -> dict[str, str]:
    profile = persona_for_instance(instance.instance_id)
    cfg = instance.config
    gateway_url = f"http://{cfg.publish_host}:{cfg.gateway_port}/"
    bridge_url = f"http://{cfg.publish_host}:{cfg.bridge_port}/"
    model_ref = model_ref_for(cfg)
    workspace_path = cfg.workspace_dir.resolve()
    config_path = cfg.config_dir.resolve()
    board_host_path = shared_board_root(instance).resolve()
    pod_name = instance.pod_name
    container_name = instance.container_name
    trio_size = max(3, instance.instance_id)

    soul = "\n".join(
        [
            WORKSPACE_MANAGED_MARKER,
            f"# SOUL.md - {profile.display_name}",
            "",
            f"あなたは {profile.display_name}。Gemma4 三人組の instance {profile.instance_id}/{trio_size} を担う {profile.title} です。",
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
        - **役割:** {profile.title}
        - **存在:** {profile.creature}
        - **雰囲気:** {profile.vibe}
        - **返答言語:** 日本語が既定
        - **補足:** 英語で話しかけられても、英語指定がなければ日本語で返す
        - **絵文字:** *
        - **アバター:** _(未設定)_
        - **しるし:** {profile.signature}
        - **主担当:** {profile.specialty}

        ## メモ

        このプロフィールは Gemma4 三人組の初期 seed です。
        いまのノリが硬すぎると思ったら、`SOUL.md` と一緒にもっと気楽に寄せてよいです。
        """
    )

    heartbeat = dedent(
        f"""\
        {WORKSPACE_MANAGED_MARKER}
        # HEARTBEAT.md - {profile.display_name}

        # 空または comment のみなら heartbeat API は無効です。
        # heartbeat を使うなら、{profile.display_name} は次を優先してください:
        # - {profile.heartbeat_focus}
        # - pod `{pod_name}`
        # - gateway `{gateway_url}`
        # - model `{model_ref}`
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
        - Shared board (container): `{CONTAINER_SHARED_BOARD_DIR}`
        - Shared board (host): `{board_host_path}`

        ## 実務メモ

        - Python は `uv` を使う
        - Instance init: `./scripts/init.ps1 --instance {profile.instance_id}`
        - Dry-run launch: `./scripts/launch.ps1 --instance {profile.instance_id} --dry-run`
        - Logs: `./scripts/logs.ps1 --instance {profile.instance_id} -Follow`

        ## この file の役割

        これは {profile.display_name} 用の cheat sheet です。環境固有の事実はここへ置き、
        共有 skill prompt には混ぜないでください。
        """
    )

    bbs = dedent(
        f"""\
        {WORKSPACE_MANAGED_MARKER}
        # BBS.md - {profile.display_name} の共有掲示板メモ

        Gemma4 三体構成には、全 scaled instance から見える共有掲示板があります。

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
        "BBS.md": bbs.strip() + "\n",
    }


def scaffold_workspace_files(instance: ScaledInstance) -> None:
    files = render_workspace_files(instance)
    for filename, content in files.items():
        path = instance.config.workspace_dir / filename
        if should_write_workspace_file(path, filename):
            path.write_text(content, encoding="utf-8")


def shared_board_root(instance: ScaledInstance) -> Path:
    return instance.config.config_dir.parent / "shared-board"


def render_shared_board_files(instance: ScaledInstance) -> dict[Path, str]:
    board_root = shared_board_root(instance)
    autochat_script = AUTOCHAT_SCRIPT_FILE.read_text(encoding="utf-8")
    render_script = BOARD_RENDER_SCRIPT_FILE.read_text(encoding="utf-8")

    readme = dedent(
        f"""\
        {BOARD_MANAGED_MARKER}
        # Shared Board

        This directory is mounted into every scaled OpenClaw pod at `{CONTAINER_SHARED_BOARD_DIR}`.
        Use it as a lightweight async board for Aster, Lyra, Noctis, and any additional scaled shards.

        ## Layout

        - `threads/<thread-id>/topic.md`
        - `threads/<thread-id>/reply-<agent>-<timestamp>.md`
        - `threads/<thread-id>/summary.md`
        - `archive/`
        - `templates/`

        ## Rules

        - Create one file per reply to avoid write collisions.
        - Do not rewrite another agent's reply file.
        - The thread starter owns `summary.md`.
        - Include the repo, exact target, current evidence, and a concrete ask in every topic.
        - Mark resolved threads in `summary.md`, then archive them when convenient.
        """
    )

    topic_template = dedent(
        f"""\
        {BOARD_MANAGED_MARKER}
        # Topic

        - Thread id:
        - Started by:
        - Repo:
        - Target files or commands:
        - Current evidence:
        - Question for siblings:
        - Desired outcome:
        """
    )

    reply_template = dedent(
        f"""\
        {BOARD_MANAGED_MARKER}
        # Reply

        - Responder:
        - Take:
        - Evidence:
        - Risks:
        - Recommendation:
        """
    )

    summary_template = dedent(
        f"""\
        {BOARD_MANAGED_MARKER}
        # Summary

        - Status: open
        - Decider:
        - Final direction:
        - Follow-up:
        """
    )

    return {
        board_root / "README.md": readme.strip() + "\n",
        board_root / "templates" / "topic-template.md": topic_template.strip() + "\n",
        board_root / "templates" / "reply-template.md": reply_template.strip() + "\n",
        board_root / "templates" / "summary-template.md": summary_template.strip() + "\n",
        board_root / "tools" / "autochat_turn.py": autochat_script if autochat_script.endswith("\n") else autochat_script + "\n",
        board_root / "tools" / "render_board_view.py": render_script if render_script.endswith("\n") else render_script + "\n",
    }


def scaffold_shared_board(instance: ScaledInstance) -> None:
    board_root = shared_board_root(instance)
    for directory in (board_root / "threads", board_root / "archive", board_root / "templates", board_root / "tools"):
        directory.mkdir(parents=True, exist_ok=True)

    for path, content in render_shared_board_files(instance).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.name in {"autochat_turn.py", "render_board_view.py"} or should_write_managed_file(path, BOARD_MANAGED_MARKER):
            path.write_text(content, encoding="utf-8")


def render_board_view(board_root: Path) -> Path:
    viewer_index = board_root / "viewer" / "index.html"
    command = [sys.executable, str(BOARD_RENDER_SCRIPT_FILE), "--board-root", str(board_root)]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise SystemExit(
            "board viewer render failed\n"
            f"command: {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return viewer_index


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


def autochat_agent_id(instance_id: int) -> str:
    return f"autochat-{persona_for_instance(instance_id).slug}"


def discuss_agent_id(instance_id: int) -> str:
    return f"discuss-{persona_for_instance(instance_id).slug}"


def autochat_seconds_offset(instance_id: int) -> int:
    return 5


def autochat_cron_expression(instance_id: int, interval_minutes: int) -> str:
    if interval_minutes < 1 or interval_minutes > 19:
        raise SystemExit("--interval-minutes must be between 1 and 19.")
    cycle_minutes = interval_minutes * 3
    minute_offset = (instance_id - 1) * interval_minutes
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
    if container_running(instance.container_name):
        return

    command = build_kube_play_command(
        instance.config,
        pod_name=instance.pod_name,
        instance_label=str(instance.instance_id),
        ensure_manifest=True,
    )
    print(f"[instance {instance.instance_id}] starting pod for discussion")
    print(command_for_display(command))
    exit_code = run_process(command, check=False)
    if exit_code != 0:
        raise SystemExit(f"Failed to start instance {instance.instance_id} (exit {exit_code}).")

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if container_running(instance.container_name):
            return
        time.sleep(1)

    raise SystemExit(f"Timed out waiting for instance {instance.instance_id} to start.")


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
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
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
    if payload is None:
        raise SystemExit(
            f"pod-local agent returned non-JSON output for instance {instance.instance_id}\n"
            f"command: {command_for_display(command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )

    return payload


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
            "main",
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


def run_autochat_job_now(instance: ScaledInstance, timeout_ms: int = 180000) -> dict[str, object]:
    job = autochat_job(instance)
    if job is None:
        raise SystemExit(f"No autochat job found for instance {instance.instance_id}.")
    return openclaw_cron_json_no_flag(
        instance,
        ["run", str(job.get("id")), "--timeout", str(timeout_ms)],
        timeout_seconds=max(120, timeout_ms // 1000 + 30),
    )

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


def ensure_object(target: dict[str, object], key: str) -> dict[str, object]:
    value = target.get(key)
    if isinstance(value, dict):
        return value
    new_value: dict[str, object] = {}
    target[key] = new_value
    return new_value


def ollama_model_spec(model_id: str) -> dict[str, object]:
    title = model_id.replace(":", " ").replace("-", " ").title()
    return {
        "id": model_id,
        "name": title,
        "reasoning": False,
        "input": ["text"],
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        "contextWindow": DEFAULT_CONTEXT_WINDOW,
        "maxTokens": DEFAULT_CONTEXT_WINDOW * 10,
    }


def model_ref_for(cfg: Config) -> str:
    return f"ollama/{cfg.ollama_model}"


def load_config_from_values(env_file: Path, raw_env: dict[str, str]) -> Config:
    merged = {**DEFAULTS, **raw_env}
    container_name = (
        merged.get("OPENCLAW_PODMAN_CONTAINER")
        or merged.get("OPENCLAW_CONTAINER")
        or DEFAULTS["OPENCLAW_CONTAINER"]
    )
    base_dir = env_file.parent
    config_dir = expand_path(merged["OPENCLAW_CONFIG_DIR"], base_dir)
    workspace_dir = expand_path(merged["OPENCLAW_WORKSPACE_DIR"], base_dir)
    state_env = parse_env_file(config_env_file(config_dir))
    gateway_token = state_env.get("OPENCLAW_GATEWAY_TOKEN") or raw_env.get("OPENCLAW_GATEWAY_TOKEN", "")
    return Config(
        env_file=env_file,
        container_name=container_name,
        image=merged["OPENCLAW_PODMAN_IMAGE"] or merged["OPENCLAW_IMAGE"],
        gateway_port=int(merged["OPENCLAW_PODMAN_GATEWAY_HOST_PORT"]),
        bridge_port=int(merged["OPENCLAW_PODMAN_BRIDGE_HOST_PORT"]),
        publish_host=merged["OPENCLAW_PODMAN_PUBLISH_HOST"],
        gateway_bind=merged["OPENCLAW_GATEWAY_BIND"],
        userns=merged["OPENCLAW_PODMAN_USERNS"],
        config_dir=config_dir,
        workspace_dir=workspace_dir,
        gateway_token=gateway_token,
        ollama_base_url=merged["OPENCLAW_OLLAMA_BASE_URL"],
        ollama_model=merged["OPENCLAW_OLLAMA_MODEL"],
        raw_env=merged,
    )


def load_config(env_file: Path) -> Config:
    raw_env = parse_env_file(env_file)
    return load_config_from_values(env_file, raw_env)


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
    model["primary"] = model_ref_for(cfg)
    sandbox = ensure_object(defaults, "sandbox")
    sandbox["mode"] = "off"

    gateway = ensure_object(payload, "gateway")
    gateway["mode"] = "local"
    control_ui = ensure_object(gateway, "controlUi")
    existing_origins = control_ui.get("allowedOrigins")
    if isinstance(existing_origins, list):
        for origin in existing_origins:
            if isinstance(origin, str) and origin not in origins:
                origins.append(origin)
    control_ui["allowedOrigins"] = origins

    models = ensure_object(payload, "models")
    providers = ensure_object(models, "providers")
    ollama = ensure_object(providers, "ollama")
    ollama["api"] = "ollama"
    ollama["baseUrl"] = cfg.ollama_base_url

    existing_models = ollama.get("models")
    preserved_models: list[dict[str, object]] = []
    seen_model_ids: set[str] = {cfg.ollama_model}
    if isinstance(existing_models, list):
        for entry in existing_models:
            if not isinstance(entry, dict):
                continue
            model_id = entry.get("id")
            if isinstance(model_id, str) and model_id not in seen_model_ids:
                seen_model_ids.add(model_id)
                preserved_models.append(entry)
    preserved_models.insert(0, ollama_model_spec(cfg.ollama_model))
    ollama["models"] = preserved_models

    tools = ensure_object(payload, "tools")
    tools["profile"] = "full"
    fs_tools = ensure_object(tools, "fs")
    fs_tools["workspaceOnly"] = False
    exec_tools = ensure_object(tools, "exec")
    apply_patch = ensure_object(exec_tools, "applyPatch")
    apply_patch["workspaceOnly"] = False

    config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def ensure_state(cfg: Config) -> Config:
    cfg.config_dir.mkdir(parents=True, exist_ok=True)
    cfg.workspace_dir.mkdir(parents=True, exist_ok=True)

    token = cfg.gateway_token.strip()
    if not token:
        token = secrets.token_urlsafe(24)

    write_or_update_env_value(config_env_file(cfg.config_dir), "OPENCLAW_GATEWAY_TOKEN", token)
    remove_env_value(cfg.env_file, "OPENCLAW_GATEWAY_TOKEN")

    ensure_openclaw_config(cfg)
    ensure_kube_manifest(cfg, instance_label="single")

    return load_config(cfg.env_file)


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
        if key in RUNTIME_ENV_EXACT or key.endswith(RUNTIME_ENV_SUFFIXES):
            pairs.append((key, value))
    if cfg.gateway_token:
        pairs.append(("OPENCLAW_GATEWAY_TOKEN", cfg.gateway_token))
    return sorted(pairs)


def redact_env_assignment(value: str) -> str:
    if "=" not in value:
        return value
    key, _ = value.split("=", 1)
    if key == "OPENCLAW_GATEWAY_TOKEN" or key.endswith("_API_KEY"):
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


def scaled_instance(env_file: Path, instance_id: int) -> ScaledInstance:
    base_env = parse_env_file(env_file)
    merged = {**DEFAULTS, **base_env}
    instance_root = scale_instance_root(merged, env_file) / instance_dir_name(instance_id)
    container_base = merged.get("OPENCLAW_PODMAN_CONTAINER") or merged.get("OPENCLAW_CONTAINER") or "openclaw"
    gateway_start = int(merged["OPENCLAW_SCALE_GATEWAY_PORT_START"])
    bridge_start = int(merged["OPENCLAW_SCALE_BRIDGE_PORT_START"])
    port_step = int(merged["OPENCLAW_SCALE_PORT_STEP"])

    raw_env = dict(base_env)
    raw_env["OPENCLAW_CONTAINER"] = f"{container_base}-{instance_id}"
    raw_env["OPENCLAW_PODMAN_CONTAINER"] = f"{container_base}-{instance_id}"
    raw_env["OPENCLAW_PODMAN_GATEWAY_HOST_PORT"] = str(gateway_start + (instance_id - 1) * port_step)
    raw_env["OPENCLAW_PODMAN_BRIDGE_HOST_PORT"] = str(bridge_start + (instance_id - 1) * port_step)
    raw_env["OPENCLAW_CONFIG_DIR"] = "."
    raw_env["OPENCLAW_WORKSPACE_DIR"] = "./workspace"

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
    write_generated_env_file(
        instance.config.env_file,
        instance.config.raw_env,
        f"# Generated for scaled instance {instance.instance_id}.",
    )
    cfg = ensure_state(load_config(instance.config.env_file))
    ensure_kube_manifest(cfg, pod_name=instance.pod_name, instance_label=str(instance.instance_id))
    resolved = ScaledInstance(
        instance_id=instance.instance_id,
        pod_name=instance.pod_name,
        container_name=instance.container_name,
        config=cfg,
    )
    scaffold_workspace_files(resolved)
    scaffold_shared_board(resolved)
    render_board_view(shared_board_root(resolved))
    return resolved


def print_scaled_instance_summary(instance: ScaledInstance) -> None:
    cfg = instance.config
    print(f"[instance {instance.instance_id}] pod={instance.pod_name} container={instance.container_name}")
    print(f"  gateway=http://{cfg.publish_host}:{cfg.gateway_port}/ bridge={cfg.publish_host}:{cfg.bridge_port}")
    print(f"  state={cfg.config_dir}")
    print(f"  shared-board={shared_board_root(instance)}")


def has_scaled_selection(args: argparse.Namespace) -> bool:
    return getattr(args, "instance", None) is not None or getattr(args, "count", None) is not None


def pod_name_for_config(cfg: Config) -> str:
    return f"{cfg.container_name}-pod"


def manifest_path_for_config(cfg: Config) -> Path:
    return cfg.config_dir / "pod.yaml"


def shared_board_root_for_config(cfg: Config, instance_label: str) -> Path | None:
    if instance_label == "single":
        return None
    return cfg.config_dir.parent / "shared-board"


def kube_manifest_for(cfg: Config, pod_name: str, instance_label: str) -> dict[str, object]:
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

    board_root = shared_board_root_for_config(cfg, instance_label)
    if board_root is not None:
        volume_mounts.append(
            {
                "name": "shared-board",
                "mountPath": CONTAINER_SHARED_BOARD_DIR,
            }
        )
        volumes.append(
            {
                "name": "shared-board",
                "hostPath": {
                    "path": podman_host_path(board_root),
                    "type": "DirectoryOrCreate",
                },
            }
        )

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
            "containers": [
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
                    "env": [{"name": key, "value": value} for key, value in runtime_env_pairs(cfg)],
                    "volumeMounts": volume_mounts,
                }
            ],
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


def build_kube_play_command(
    cfg: Config,
    pod_name: str | None = None,
    instance_label: str = "single",
    ensure_manifest: bool = True,
) -> list[str]:
    manifest_path = manifest_path_for_config(cfg)
    if ensure_manifest:
        manifest_path = ensure_kube_manifest(cfg, pod_name=pod_name, instance_label=instance_label)
    command = [podman_bin(), "kube", "play", "--replace", "--no-pod-prefix"]
    if cfg.userns:
        command.extend(["--userns", cfg.userns])
    command.append(str(manifest_path))
    return command


def build_kube_down_command(cfg: Config) -> list[str]:
    return [podman_bin(), "kube", "down", str(manifest_path_for_config(cfg))]


def run_process(command: list[str], check: bool = True) -> int:
    completed = subprocess.run(command, check=False)
    if check and completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed.returncode


def print_kv(title: str, value: str) -> None:
    print(f"{title}: {value}")


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
    print_kv("ollama base url", cfg.ollama_base_url)
    print_kv("default model", model_ref_for(cfg))
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
    checks.append(("OLLAMA_API_KEY", bool(cfg.raw_env.get("OLLAMA_API_KEY", "").strip()), "set a placeholder like ollama-local"))
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
    print_kv("ollama base url", cfg.ollama_base_url)
    print_kv("default model", model_ref_for(cfg))
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
            else:
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
        print_kv("shared board dir", str(shared_board_root(instance)))
        print_kv("ollama base url", cfg.ollama_base_url)
        print_kv("default model", model_ref_for(cfg))
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
    print_kv("ollama base url", cfg.ollama_base_url)
    print_kv("default model", model_ref_for(cfg))
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
        description="Concept helper for running OpenClaw with Podman.",
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

    discuss_parser = subparsers.add_parser("discuss", help="Run a pod-local shared-board discussion across scaled instances.")
    discuss_parser.add_argument("--topic", required=True, help="Discussion topic to seed into the shared board.")
    discuss_parser.add_argument("--thread-id", help="Optional explicit thread id (letters, numbers, dashes).")
    discuss_parser.add_argument("--count", type=int, help="Number of scaled instances to include (default: 3).")
    discuss_parser.add_argument("--starter", type=int, default=1, help="Instance id that opens and closes the thread (default: 1).")
    discuss_parser.add_argument("--timeout", type=int, default=180, help="Per-agent timeout in seconds (default: 180).")
    discuss_parser.set_defaults(func=cmd_discuss)

    autochat_parser = subparsers.add_parser("autochat", help="Manage always-on shared-board autochat jobs inside scaled pods.")
    autochat_subparsers = autochat_parser.add_subparsers(dest="autochat_command", required=True)

    autochat_enable_parser = autochat_subparsers.add_parser("enable", help="Create or replace pod-local cron jobs for always-on autochat.")
    autochat_enable_parser.add_argument("--count", type=int, help="Scaled instance count to manage (must be 3; default: 3).")
    autochat_enable_parser.add_argument("--interval-minutes", type=int, default=2, help="Minute gap between speakers; full cycle is gap*3 (default: 2).")
    autochat_enable_parser.add_argument("--timeout", type=int, default=180, help="Per-turn timeout seconds (default: 180).")
    autochat_enable_parser.set_defaults(func=cmd_autochat_enable)

    autochat_status_parser = autochat_subparsers.add_parser("status", help="Show pod-local autochat cron status.")
    autochat_status_parser.add_argument("--count", type=int, help="Scaled instance count to inspect (must be 3; default: 3).")
    autochat_status_parser.set_defaults(func=cmd_autochat_status)

    autochat_run_now_parser = autochat_subparsers.add_parser("run-now", help="Enqueue one immediate autochat turn for each pod-local job.")
    autochat_run_now_parser.add_argument("--count", type=int, help="Scaled instance count to trigger (must be 3; default: 3).")
    autochat_run_now_parser.add_argument("--timeout-ms", type=int, default=180000, help="Cron run request timeout in ms (default: 180000).")
    autochat_run_now_parser.add_argument("--wait-seconds", type=int, default=10, help="Wait this many seconds before listing live-thread files (default: 10).")
    autochat_run_now_parser.set_defaults(func=cmd_autochat_run_now)

    autochat_disable_parser = autochat_subparsers.add_parser("disable", help="Remove pod-local autochat cron jobs.")
    autochat_disable_parser.add_argument("--count", type=int, help="Scaled instance count to disable (must be 3; default: 3).")
    autochat_disable_parser.set_defaults(func=cmd_autochat_disable)

    boardview_parser = subparsers.add_parser("boardview", help="Build a human-readable shared-board HTML viewer.")
    boardview_parser.add_argument("--thread", help="Optional thread id to print/open directly.")
    boardview_parser.add_argument("--open", action="store_true", help="Open the rendered HTML on Windows.")
    boardview_parser.set_defaults(func=cmd_boardview)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.env_file = Path(args.env_file).resolve()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
