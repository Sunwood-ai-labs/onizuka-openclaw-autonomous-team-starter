from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from openclaw_podman_starter import cli

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

RENDER_BOARD_VIEW_PATH = Path(__file__).resolve().parents[1] / "scripts" / "render_board_view.py"
render_board_view_spec = importlib.util.spec_from_file_location("render_board_view", RENDER_BOARD_VIEW_PATH)
render_board_view = importlib.util.module_from_spec(render_board_view_spec)
assert render_board_view_spec and render_board_view_spec.loader
sys.modules[render_board_view_spec.name] = render_board_view
render_board_view_spec.loader.exec_module(render_board_view)

SHARED_BOARD_SERVICE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "shared_board_service.py"
shared_board_service_spec = importlib.util.spec_from_file_location("shared_board_service", SHARED_BOARD_SERVICE_PATH)
shared_board_service = importlib.util.module_from_spec(shared_board_service_spec)
assert shared_board_service_spec and shared_board_service_spec.loader
sys.modules[shared_board_service_spec.name] = shared_board_service
shared_board_service_spec.loader.exec_module(shared_board_service)

MATTERMOST_GET_STATE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mattermost_get_state.py"
mattermost_get_state_spec = importlib.util.spec_from_file_location("mattermost_get_state", MATTERMOST_GET_STATE_PATH)
mattermost_get_state = importlib.util.module_from_spec(mattermost_get_state_spec)
assert mattermost_get_state_spec and mattermost_get_state_spec.loader
sys.modules[mattermost_get_state_spec.name] = mattermost_get_state
mattermost_get_state_spec.loader.exec_module(mattermost_get_state)


def write_env_file(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "OPENCLAW_CONTAINER=openclaw",
                "OPENCLAW_PODMAN_CONTAINER=openclaw",
                "OPENCLAW_PODMAN_PUBLISH_HOST=127.0.0.1",
                "OPENCLAW_SCALE_INSTANCE_ROOT=./instances",
                "OPENCLAW_OLLAMA_MODEL=gemma4:e2b",
                "OPENCLAW_OLLAMA_BASE_URL=http://127.0.0.1:11434",
                "OLLAMA_API_KEY=ollama-local",
                "",
            ]
        ),
        encoding="utf-8",
    )


class CliTests(unittest.TestCase):
    def test_render_board_view_formats_key_value_lines(self) -> None:
        html = render_board_view.markdown_to_html(
            "\n".join(
                [
                    "responder: つむぎ",
                    "observation: Something changed",
                    "proposal: Ship the fix",
                ]
            )
        )
        self.assertIn('<dl class="kv-list">', html)
        self.assertIn("<dt>responder</dt>", html)
        self.assertIn("<dd>つむぎ</dd>", html)
        self.assertIn("<dt>proposal</dt>", html)

    def test_render_board_view_structures_chat_like_cards(self) -> None:
        html = render_board_view.structured_chat_html(
            "\n".join(
                [
                    "responder: つむぎ",
                    "observation: Something changed",
                    "proposal: Ship the fix",
                    "handoff question to さく: What do you think?",
                ]
            )
        )
        assert html is not None
        self.assertIn('class="chat-card"', html)
        self.assertIn("Just noticed", html)
        self.assertIn("Thinking", html)
        self.assertIn("Throwing it over", html)

    def test_render_board_view_uses_ascii_separator_in_header(self) -> None:
        message = render_board_view.ThreadMessage(
            path=Path("turn-lyra.md"),
            kind="turn",
            speaker="lyra",
            timestamp_label="2026-04-08 22:28:59",
            html_body="<p>Body</p>",
            raw_text="Body",
        )
        html = render_board_view.bubble_html(message)
        self.assertIn("つむぎ | gemma4:e2b", html)
        self.assertNotIn("·", html)

    def test_autochat_helpers(self) -> None:
        self.assertEqual(cli.autochat_job_name(1), "shared-board-autochat-001")
        self.assertEqual(cli.autochat_cron_expression(1, 2), "5 0-59/6 * * * *")
        self.assertEqual(cli.autochat_cron_expression(2, 2), "5 2-59/6 * * * *")
        self.assertEqual(cli.autochat_cron_expression(3, 2), "5 4-59/6 * * * *")
        self.assertEqual(cli.previous_speaker(1), "noctis")
        self.assertEqual(cli.previous_speaker(2), "aster")
        self.assertEqual(cli.previous_speaker(3), "lyra")
        self.assertEqual(cli.mattermost_lounge_job_name(1), "mattermost-lounge-autochat-001")
        self.assertEqual(cli.mattermost_lounge_agent_id(2), "mattermost-lounge-tsumugi")

    def test_mattermost_lounge_prompt_mentions_action_scripts(self) -> None:
        instance = cli.ScaledInstance(
            instance_id=1,
            pod_name="openclaw-1-pod",
            container_name="openclaw-1",
            config=cli.Config(
                env_file=Path("D:/tmp/.env"),
                container_name="openclaw-1",
                image="image",
                gateway_port=18789,
                bridge_port=18790,
                board_port=18889,
                publish_host="127.0.0.1",
                network="podman",
                gateway_bind="lan",
                userns="keep-id",
                config_dir=Path("D:/tmp/instances/agent_001"),
                workspace_dir=Path("D:/tmp/instances/agent_001/workspace"),
                gateway_token="token",
                ollama_base_url="http://127.0.0.1:11434",
                ollama_model="gemma4:e2b",
                board_image="python:3.11-slim",
                raw_env={},
            ),
        )
        prompt = cli.build_mattermost_lounge_turn_prompt(instance)
        self.assertIn("mattermost_dispatch_turn.py", prompt)
        self.assertIn("他のコマンドは実行しないでください", prompt)
        self.assertIn("stdout だけをそのまま返答してください", prompt)

    def test_latest_assistant_text_ignores_non_assistant_entries(self) -> None:
        payload = {
            "payloads": [
                {"role": "tool", "text": "tool output"},
                {"role": "assistant", "text": "python3 /tmp/example.py"},
                {"role": "assistant", "text": "POSTED abc123"},
            ]
        }
        self.assertEqual(cli.latest_assistant_text(payload), "POSTED abc123")

    def test_mattermost_get_state_builds_suggested_reaction(self) -> None:
        rate_limit = {"limited": False, "reason": "ok"}
        channels = [
            {
                "channel_name": "triad-lab",
                "threads": [
                    {
                        "last_handle": "saku",
                        "last_post_id": "post123",
                        "last_ts": 100,
                        "root_preview": "meaningful",
                    }
                ],
            }
        ]
        suggested = mattermost_get_state.build_suggested_next(
            1,
            default_channel="triad-lab",
            rate_limit=rate_limit,
            channel_summaries=channels,
        )
        self.assertEqual(suggested["kind"], "reaction")
        self.assertIn("mattermost_add_reaction.py", suggested["command"])
        self.assertIn("post123", suggested["command"])

    def test_mattermost_get_state_builds_public_channel_creation_for_tsumugi(self) -> None:
        suggested = mattermost_get_state.build_suggested_next(
            2,
            default_channel="triad-lab",
            rate_limit={"limited": False, "reason": "ok"},
            channel_summaries=[
                {
                    "channel_name": "triad-lab",
                    "threads": [],
                }
            ],
        )
        self.assertEqual(suggested["kind"], "create_channel")
        self.assertIn("mattermost_create_channel.py", suggested["command"])
        self.assertIn("triad-open-room", suggested["command"])
        self.assertIn("mattermost_post_message.py", suggested["followup_command"])

    def test_mattermost_get_state_builds_idle_when_rate_limited(self) -> None:
        suggested = mattermost_get_state.build_suggested_next(
            2,
            default_channel="triad-lab",
            rate_limit={"limited": True, "reason": "cooldown"},
            channel_summaries=[],
        )
        self.assertEqual(suggested["kind"], "idle")
        self.assertEqual(suggested["final_text"], "IDLE cooldown")

    def test_mattermost_get_state_persona_post_variants_differ(self) -> None:
        msg1 = mattermost_get_state.pick_post_message(mattermost_get_state.default_persona_config(1), 0)
        msg2 = mattermost_get_state.pick_post_message(mattermost_get_state.default_persona_config(2), 0)
        msg3 = mattermost_get_state.pick_post_message(mattermost_get_state.default_persona_config(3), 0)
        self.assertNotEqual(msg1, msg2)
        self.assertNotEqual(msg2, msg3)
        self.assertNotEqual(msg1, msg3)

    def test_mattermost_get_state_parses_workspace_persona_block(self) -> None:
        text = """
## Mattermost Persona
```json
{
  "reaction_emoji": "eyes",
  "channel_preference": ["triad-lab", "triad-free-talk"],
  "post_variants": ["a", "b"],
  "auto_public_channel": null
}
```
"""
        payload = mattermost_get_state.parse_workspace_persona_block(text)
        self.assertEqual(payload["reaction_emoji"], "eyes")
        self.assertEqual(payload["channel_preference"][1], "triad-free-talk")
        self.assertEqual(payload["post_variants"][0], "a")

    def test_mattermost_get_state_prefers_non_self_reaction_candidates(self) -> None:
        channels = [
            {
                "channel_name": "triad-lab",
                "threads": [
                    {
                        "last_handle": "saku",
                        "last_post_id": "self-post",
                        "last_ts": 300,
                        "root_preview": "meaningful",
                    }
                ],
            },
            {
                "channel_name": "triad-free-talk",
                "threads": [
                    {
                        "last_handle": "iori",
                        "last_post_id": "other-post",
                        "last_ts": 200,
                        "root_preview": "meaningful",
                    }
                ],
            },
        ]
        suggested = mattermost_get_state.build_suggested_next(
            3,
            default_channel="triad-lab",
            rate_limit={"limited": False, "reason": "ok"},
            channel_summaries=channels,
        )
        self.assertEqual(suggested["kind"], "reaction")
        self.assertIn("other-post", suggested["command"])

    def test_mattermost_get_state_prefers_alternate_post_channel_when_self_was_latest(self) -> None:
        channel = mattermost_get_state.preferred_post_channel(
            {
                "handle": "saku",
                "channel_preference": ["triad-free-talk", "triad-lab"],
            },
            "triad-lab",
            [
                {
                    "channel_name": "triad-lab",
                    "threads": [{"last_handle": "saku"}],
                },
                {
                    "channel_name": "triad-free-talk",
                    "threads": [{"last_handle": "iori"}],
                },
            ],
        )
        self.assertEqual(channel["channel_name"], "triad-free-talk")

    def test_discussion_thread_helpers(self) -> None:
        thread_id = cli.slugify_thread_id("Gemma4 Board: QA Smoke!!")
        self.assertEqual(thread_id, "gemma4-board-qa-smoke")

        thread = cli.discussion_thread(Path("D:/tmp/shared-board"), "qa-thread")
        reply_path = cli.discussion_reply_path(
            thread,
            cli.ScaledInstance(
                instance_id=2,
                pod_name="openclaw-2-pod",
                container_name="openclaw-2",
                config=cli.Config(
                    env_file=Path("D:/tmp/.env"),
                    container_name="openclaw-2",
                    image="image",
                    gateway_port=18791,
                    bridge_port=18792,
                    board_port=18891,
                    publish_host="127.0.0.1",
                    network="podman",
                    gateway_bind="lan",
                    userns="keep-id",
                    config_dir=Path("D:/tmp/instances/agent_002"),
                    workspace_dir=Path("D:/tmp/instances/agent_002/workspace"),
                    gateway_token="token",
                    ollama_base_url="http://127.0.0.1:11434",
                    ollama_model="gemma4:e2b",
                    board_image="python:3.11-slim",
                    raw_env={},
                ),
            ),
            "20260408T000000Z",
        )

        self.assertEqual(thread.thread_dir, Path("D:/tmp/shared-board/threads/qa-thread"))
        self.assertEqual(thread.topic_path, Path("D:/tmp/shared-board/threads/qa-thread/topic.md"))
        self.assertEqual(thread.summary_path, Path("D:/tmp/shared-board/threads/qa-thread/summary.md"))
        self.assertEqual(reply_path, Path("D:/tmp/shared-board/threads/qa-thread/reply-lyra-20260408T000000Z.md"))

    def test_scaled_instance_state_seeds_triads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)

            expected = {1: "いおり", 2: "つむぎ", 3: "さく"}
            for instance_id, name in expected.items():
                resolved = cli.ensure_scaled_instance_state(cli.scaled_instance(env_file, instance_id))
                soul_path = resolved.config.workspace_dir / "SOUL.md"
                identity_path = resolved.config.workspace_dir / "IDENTITY.md"
                bbs_path = resolved.config.workspace_dir / "BBS.md"
                soul_text = soul_path.read_text(encoding="utf-8")
                identity_text = identity_path.read_text(encoding="utf-8")
                bbs_text = bbs_path.read_text(encoding="utf-8")
                self.assertTrue(soul_path.exists())
                self.assertTrue(identity_path.exists())
                self.assertTrue(bbs_path.exists())
                self.assertIn(f"# SOUL.md - {name}", soul_text)
                self.assertIn("- ユーザーが別言語を明示しない限り、日本語で返答する。", soul_text)
                self.assertIn("- かしこまりすぎず、同じチームで話す感じでいく。", soul_text)
                self.assertIn(cli.CONTAINER_SHARED_BOARD_DIR, soul_text)
                self.assertIn(f"**名前:** {name}", identity_text)
                self.assertIn("**返答言語:** 日本語が既定", identity_text)
                self.assertIn("もっと気楽に寄せてよい", identity_text)
                self.assertIn(f"# BBS.md - {name} の共有掲示板メモ", bbs_text)
                self.assertIn("軽い相談や雑談の投げ込みでも使っていい。", bbs_text)
                self.assertEqual(resolved.config.config_dir.name, f"agent_{instance_id:03d}")

    def test_scaled_instance_state_seeds_shared_board_and_manifest_mount(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)

            resolved = cli.ensure_scaled_instance_state(cli.scaled_instance(env_file, 2))
            board_root = cli.shared_board_root(resolved)
            manifest = json.loads((resolved.config.config_dir / "pod.yaml").read_text(encoding="utf-8"))
            board_manifest = json.loads((resolved.config.config_dir / "board-pod.yaml").read_text(encoding="utf-8"))

            self.assertTrue((board_root / "README.md").exists())
            self.assertTrue((board_root / "threads").exists())
            self.assertTrue((board_root / "archive").exists())
            self.assertTrue((board_root / "templates" / "topic-template.md").exists())
            self.assertTrue((board_root / "tools" / "autochat_turn.py").exists())
            self.assertTrue((board_root / "tools" / "mattermost_autochat_turn.py").exists())
            self.assertTrue((board_root / "tools" / "mattermost_get_state.py").exists())
            self.assertTrue((board_root / "tools" / "mattermost_post_message.py").exists())
            self.assertTrue((board_root / "tools" / "mattermost_create_channel.py").exists())
            self.assertTrue((board_root / "tools" / "mattermost_add_reaction.py").exists())
            self.assertTrue((board_root / "tools" / "mattermost_dispatch_turn.py").exists())
            self.assertTrue((board_root / "tools" / "render_board_view.py").exists())
            self.assertTrue((board_root / "tools" / "shared_board_service.py").exists())
            self.assertTrue((board_root / "tools" / "shared_board_app.html").exists())
            self.assertTrue((board_root / "viewer" / "index.html").exists())

            main_containers = manifest["spec"]["containers"]
            board_containers = board_manifest["spec"]["containers"]
            volume_mounts = main_containers[0]["volumeMounts"]
            volumes = manifest["spec"]["volumes"]
            board_volumes = board_manifest["spec"]["volumes"]
            self.assertIn(
                {"name": "shared-board", "mountPath": cli.CONTAINER_SHARED_BOARD_DIR},
                volume_mounts,
            )
            self.assertIn(
                {
                    "name": "shared-board",
                    "hostPath": {
                        "path": cli.podman_host_path(board_root),
                        "type": "DirectoryOrCreate",
                    },
                },
                volumes,
            )
            self.assertIn(
                {
                    "name": "shared-board",
                    "hostPath": {
                        "path": cli.podman_host_path(board_root),
                        "type": "DirectoryOrCreate",
                    },
                },
                board_volumes,
            )
            self.assertEqual(len(main_containers), 1)
            self.assertEqual(main_containers[0]["name"], "openclaw-2")
            self.assertEqual(board_manifest["metadata"]["name"], "openclaw-2-board-pod")
            self.assertEqual(len(board_containers), 1)
            self.assertEqual(board_containers[0]["name"], "openclaw-2-board")
            self.assertEqual(board_containers[0]["image"], "python:3.11-slim")
            self.assertEqual(board_containers[0]["ports"][0]["hostPort"], 18891)
            self.assertEqual(
                board_containers[0]["command"][:6],
                [
                    "python",
                    f"{cli.CONTAINER_SHARED_BOARD_DIR}/tools/shared_board_service.py",
                    "--board-root",
                    cli.CONTAINER_SHARED_BOARD_DIR,
                    "--db-path",
                    cli.CONTAINER_BOARD_DB_PATH,
                ],
            )

    def test_shared_board_service_syncs_threads_into_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            board_root = temp_root / "shared-board"
            thread_dir = board_root / "threads" / "qa-thread"
            thread_dir.mkdir(parents=True)

            (thread_dir / "topic.md").write_text(
                "# QA Thread\n\nStarted by: Operator\n\nCheck the board sidecar.\n",
                encoding="utf-8",
            )
            (thread_dir / "reply-visitor-20260409T010203Z.md").write_text(
                "Responder: Visitor\n\nLooks healthy.\n",
                encoding="utf-8",
            )

            repo = shared_board_service.BoardRepository(board_root, temp_root / "cache" / "board.sqlite3")
            repo.initialize()

            listing = repo.list_threads()
            self.assertEqual(len(listing["threads"]), 1)
            self.assertEqual(listing["threads"][0]["threadId"], "qa-thread")
            self.assertEqual(listing["threads"][0]["title"], "QA Thread")

            detail = repo.get_thread("qa-thread")
            self.assertEqual(len(detail["thread"]["posts"]), 2)
            author_labels = {post["authorLabel"] for post in detail["thread"]["posts"]}
            self.assertIn("Operator", author_labels)
            self.assertIn("Visitor", author_labels)

            created = repo.create_post("qa-thread", "Another reply from the browser.", "DeskUser")
            self.assertEqual(created["thread"]["threadId"], "qa-thread")
            self.assertEqual(len(created["thread"]["posts"]), 3)
            reply_files = sorted(thread_dir.glob("reply-visitor-*.md"))
            self.assertEqual(len(reply_files), 2)

    def test_scaled_launch_dry_run_has_no_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)

            args = argparse.Namespace(
                env_file=env_file,
                dry_run=True,
                no_init=False,
                instance=None,
                count=3,
            )

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = cli.cmd_launch(args)

            self.assertEqual(exit_code, 0)
            self.assertRegex(output.getvalue().lower(), r"\bpodman(?:\.exe)? kube play\b")
            self.assertIn("--network", output.getvalue().lower())
            self.assertIn("board-pod.yaml", output.getvalue().lower())
            self.assertFalse((temp_root / "instances").exists())

    def test_mattermost_token_is_injected_into_scaled_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)

            mattermost_root = temp_root / ".openclaw" / "mattermost"
            mattermost_root.mkdir(parents=True)
            (mattermost_root / "state.env").write_text(
                "OPENCLAW_MATTERMOST_BOT_TOKEN_002=mm-token-2\n",
                encoding="utf-8",
            )

            instance = cli.scaled_instance(env_file, 2)
            self.assertEqual(instance.config.raw_env["OPENCLAW_MATTERMOST_BOT_TOKEN"], "mm-token-2")
            self.assertEqual(instance.config.raw_env["OPENCLAW_MATTERMOST_ENABLED"], "true")

    def test_ensure_openclaw_config_writes_mattermost_channel_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)
            env_text = env_file.read_text(encoding="utf-8")
            env_text += "\n".join(
                [
                    "OPENCLAW_MATTERMOST_ENABLED=true",
                    "OPENCLAW_MATTERMOST_BASE_URL=http://mattermost:8065",
                    "OPENCLAW_MATTERMOST_BOT_TOKEN=test-bot-token",
                    "",
                ]
            )
            env_file.write_text(env_text, encoding="utf-8")

            cfg = cli.ensure_state(cli.load_config(env_file))
            payload = json.loads((cfg.config_dir / "openclaw.json").read_text(encoding="utf-8"))

            self.assertEqual(payload["channels"]["mattermost"]["enabled"], True)
            self.assertEqual(payload["channels"]["mattermost"]["baseUrl"], "http://mattermost:8065")
            self.assertEqual(payload["channels"]["mattermost"]["botToken"], "test-bot-token")
            self.assertEqual(payload["channels"]["mattermost"]["chatmode"], "oncall")
            self.assertEqual(payload["channels"]["mattermost"]["groups"]["*"]["requireMention"], True)
            self.assertEqual(payload["channels"]["mattermost"]["network"]["dangerouslyAllowPrivateNetwork"], True)
            self.assertEqual(payload["plugins"]["entries"]["mattermost"]["enabled"], True)

    def test_load_mattermost_config_uses_default_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)

            cfg = cli.load_mattermost_config(env_file)

            self.assertEqual(cfg.network, cli.DEFAULT_PODMAN_NETWORK)
            self.assertEqual(cli.mattermost_host_url(cfg), "http://127.0.0.1:8065")
            expected_manifest = os.path.normcase(os.path.realpath(str(temp_root / ".openclaw" / "mattermost" / "pod.yaml")))
            actual_manifest = os.path.normcase(os.path.realpath(str(cli.mattermost_manifest_path(cfg))))
            self.assertEqual(actual_manifest, expected_manifest)

    def test_mattermost_persona_usernames_use_romanized_handles(self) -> None:
        self.assertEqual(cli.mattermost_persona_username(1), "iori")
        self.assertEqual(cli.mattermost_persona_username(2), "tsumugi")
        self.assertEqual(cli.mattermost_persona_username(3), "saku")

    def test_mattermost_persona_avatar_files_exist(self) -> None:
        self.assertEqual(cli.mattermost_persona_avatar_file(1).name, "iori.png")
        self.assertEqual(cli.mattermost_persona_avatar_file(2).name, "tsumugi.png")
        self.assertEqual(cli.mattermost_persona_avatar_file(3).name, "saku.png")
        self.assertTrue(cli.mattermost_persona_avatar_file(1).exists())
        self.assertTrue(cli.mattermost_persona_avatar_file(2).exists())
        self.assertTrue(cli.mattermost_persona_avatar_file(3).exists())


if __name__ == "__main__":
    unittest.main()
