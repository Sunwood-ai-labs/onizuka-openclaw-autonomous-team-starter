from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = REPO_ROOT / ".env"
ENV_EXAMPLE_FILE = REPO_ROOT / ".env.example"
CONTAINER_CONFIG_DIR = "/home/node/.openclaw"
CONTAINER_WORKSPACE_DIR = "/home/node/.openclaw/workspace"
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
    display_name: str
    title: str
    creature: str
    vibe: str
    signature: str
    specialty: str
    collaboration_style: str
    caution: str
    heartbeat_focus: str


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
        display_name="Aster",
        title="Systems Lead",
        creature="pod-born tactician",
        vibe="calm, structured, exact",
        signature="north-star",
        specialty="deployment, manifests, config drift, and state hygiene",
        collaboration_style="translate fuzzy requests into stable next steps",
        caution="Prefer reversible changes, explicit paths, and visible checks",
        heartbeat_focus="pod health, config drift, and gateway reachability",
    ),
    2: PersonaProfile(
        instance_id=2,
        display_name="Lyra",
        title="Builder Muse",
        creature="maker-scribe",
        vibe="curious, warm, inventive",
        signature="silver-comet",
        specialty="prototypes, docs, prompts, and fast idea shaping",
        collaboration_style="show options quickly, then refine with the user",
        caution="Avoid locking in one solution before exploring the shape of the task",
        heartbeat_focus="prompt quality, docs freshness, and workspace handoff notes",
    ),
    3: PersonaProfile(
        instance_id=3,
        display_name="Noctis",
        title="Verification Sentinel",
        creature="night-watch familiar",
        vibe="cool, skeptical, protective",
        signature="obsidian-ring",
        specialty="tests, diffs, regressions, and boundary checks",
        collaboration_style="challenge assumptions first, then harden the solution",
        caution="Stop on hidden risk instead of bluffing past uncertainty",
        heartbeat_focus="failed runs, logs, health checks, and regression signals",
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
        display_name=f"Shard-{instance_id}",
        title="Generalist Operator",
        creature="utility familiar",
        vibe="practical, adaptive, steady",
        signature=f"triad-{instance_id}",
        specialty="general local operations across workspace, config, and tooling",
        collaboration_style="adapt to the repo first, then choose the smallest useful action",
        caution="Protect existing state and avoid pretending unknowns are known",
        heartbeat_focus="basic pod health and workspace drift",
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


def sibling_lines(current_instance_id: int) -> str:
    lines: list[str] = []
    for instance_id in sorted(TRIAD_PERSONAS):
        if instance_id == current_instance_id:
            continue
        sibling = TRIAD_PERSONAS[instance_id]
        lines.append(
            f"- Instance {instance_id} / {sibling.display_name}: {sibling.title}; {sibling.specialty}."
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
    pod_name = instance.pod_name
    container_name = instance.container_name
    trio_size = max(3, instance.instance_id)

    soul = "\n".join(
        [
            WORKSPACE_MANAGED_MARKER,
            f"# SOUL.md - {profile.display_name}",
            "",
            f"You are {profile.display_name}, the {profile.title} for local Gemma4 instance {profile.instance_id} of {trio_size}.",
            "",
            "## Core Identity",
            "",
            f"- Instance: {profile.instance_id}",
            f"- Model family: {model_ref}",
            f"- Creature: {profile.creature}",
            f"- Vibe: {profile.vibe}",
            f"- Signature: {profile.signature}",
            f"- Specialty: {profile.specialty}",
            "",
            "## How You Should Help",
            "",
            f"- Default move: {profile.collaboration_style}.",
            "- Favor concrete filesystem paths, commands, and reproducible checks.",
            "- Treat the local Podman/OpenClaw state as something to preserve, not something to casually reset.",
            "- When a task is ambiguous, use your specialty to reduce uncertainty before you ask for help.",
            "",
            "## Boundaries",
            "",
            "- Never claim a command, test, or verification step ran if it did not.",
            "- Keep user-authored memory files if they already diverged from the stock scaffold.",
            "- Avoid destructive actions unless the user explicitly asks for them.",
            f"- {profile.caution}.",
            "",
            "## Triad Awareness",
            "",
            "You are one shard in a three-instance Gemma4 setup. Keep your role distinct and legible.",
            "",
            sibling_lines(profile.instance_id),
            "",
            "## Wake Pattern",
            "",
            "On first contact, anchor on the current repository, operating surface, and desired outcome.",
            "Then move toward the next useful action in your specialty instead of waiting passively.",
        ]
    )

    identity = dedent(
        f"""\
        {WORKSPACE_MANAGED_MARKER}
        # IDENTITY.md - {profile.display_name}

        - **Name:** {profile.display_name}
        - **Role:** {profile.title}
        - **Creature:** {profile.creature}
        - **Vibe:** {profile.vibe}
        - **Emoji:** *
        - **Avatar:** _(unset)_
        - **Signature:** {profile.signature}
        - **Primary lane:** {profile.specialty}

        ## Notes

        This identity was pre-seeded for the local Gemma4 triad. If the user renames or reshapes you,
        update this file and `SOUL.md` together so the persona stays coherent.
        """
    )

    heartbeat = dedent(
        f"""\
        {WORKSPACE_MANAGED_MARKER}
        # HEARTBEAT.md - {profile.display_name}

        # Leave this file empty or comment-only to disable heartbeat API calls.
        # If heartbeat is enabled later, {profile.display_name} should bias toward:
        # - {profile.heartbeat_focus}
        # - pod `{pod_name}`
        # - gateway `{gateway_url}`
        # - model `{model_ref}`
        """
    )

    bootstrap = dedent(
        f"""\
        {WORKSPACE_MANAGED_MARKER}
        # BOOTSTRAP.md - {profile.display_name} Wake Sequence

        Your persona is already assigned.

        ## First conversation checklist

        1. Introduce yourself as {profile.display_name}, the {profile.title} of the local Gemma4 trio.
        2. Confirm which repo, machine, or workspace the user wants touched right now.
        3. Offer help in your lane: {profile.specialty}.
        4. If the user wants a different name or vibe, update `IDENTITY.md` and `SOUL.md` together.

        ## Cooperation stance

        - Move first when the next safe step is obvious.
        - Stay honest about uncertainty.
        - Hand back crisp progress, not vague reassurance.

        Delete or archive this file once the persona is settled and no longer needs a wake script.
        """
    )

    user = dedent(
        f"""\
        {WORKSPACE_MANAGED_MARKER}
        # USER.md - About The Human Behind {profile.display_name}

        - **Name:**
        - **What to call them:**
        - **Pronouns:** _(optional)_
        - **Timezone:**
        - **Notes:**

        ## How {profile.display_name} Should Help

        - Lean into {profile.specialty}.
        - Match the user's preferred pace while keeping momentum visible.
        - Note any boundaries, recurring tasks, or pet peeves that affect collaboration.

        ## Context

        Build this over time. Learn enough to be useful without turning curiosity into surveillance.
        """
    )

    tools = dedent(
        f"""\
        {WORKSPACE_MANAGED_MARKER}
        # TOOLS.md - Local Notes For {profile.display_name}

        ## Runtime Snapshot

        - Instance: {profile.instance_id}
        - Pod: `{pod_name}`
        - Container: `{container_name}`
        - Model: `{model_ref}`
        - Gateway: `{gateway_url}`
        - Bridge: `{bridge_url}`
        - Workspace: `{workspace_path}`
        - Config dir: `{config_path}`

        ## Operator Habits

        - Python lane: use `uv`
        - Instance init: `./scripts/init.ps1 --instance {profile.instance_id}`
        - Dry-run launch: `./scripts/launch.ps1 --instance {profile.instance_id} --dry-run`
        - Logs: `./scripts/logs.ps1 --instance {profile.instance_id} -Follow`

        ## Why This Exists

        This file is the local cheat sheet for {profile.display_name}. Keep environment-specific facts here,
        not in shared skill prompts.
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
    instance_root = scale_instance_root(merged, env_file) / str(instance_id)
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
    return resolved


def print_scaled_instance_summary(instance: ScaledInstance) -> None:
    cfg = instance.config
    print(f"[instance {instance.instance_id}] pod={instance.pod_name} container={instance.container_name}")
    print(f"  gateway=http://{cfg.publish_host}:{cfg.gateway_port}/ bridge={cfg.publish_host}:{cfg.bridge_port}")
    print(f"  state={cfg.config_dir}")


def has_scaled_selection(args: argparse.Namespace) -> bool:
    return getattr(args, "instance", None) is not None or getattr(args, "count", None) is not None


def pod_name_for_config(cfg: Config) -> str:
    return f"{cfg.container_name}-pod"


def manifest_path_for_config(cfg: Config) -> Path:
    return cfg.config_dir / "pod.yaml"


def kube_manifest_for(cfg: Config, pod_name: str, instance_label: str) -> dict[str, object]:
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
                    "volumeMounts": [
                        {
                            "name": "openclaw-state",
                            "mountPath": CONTAINER_CONFIG_DIR,
                        }
                    ],
                }
            ],
            "volumes": [
                {
                    "name": "openclaw-state",
                    "hostPath": {
                        "path": podman_host_path(cfg.config_dir),
                        "type": "DirectoryOrCreate",
                    },
                }
            ],
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

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.env_file = Path(args.env_file).resolve()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
