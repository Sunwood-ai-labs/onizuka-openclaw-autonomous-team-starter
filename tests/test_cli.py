from __future__ import annotations

import argparse
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from openclaw_podman_starter import cli


RENDER_BOARD_VIEW_PATH = Path(__file__).resolve().parents[1] / "scripts" / "render_board_view.py"
render_board_view_spec = importlib.util.spec_from_file_location("render_board_view", RENDER_BOARD_VIEW_PATH)
render_board_view = importlib.util.module_from_spec(render_board_view_spec)
assert render_board_view_spec and render_board_view_spec.loader
sys.modules[render_board_view_spec.name] = render_board_view
render_board_view_spec.loader.exec_module(render_board_view)


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
                    "responder: Lyra",
                    "observation: Something changed",
                    "proposal: Ship the fix",
                ]
            )
        )
        self.assertIn('<dl class="kv-list">', html)
        self.assertIn("<dt>responder</dt>", html)
        self.assertIn("<dd>Lyra</dd>", html)
        self.assertIn("<dt>proposal</dt>", html)

    def test_render_board_view_structures_chat_like_cards(self) -> None:
        html = render_board_view.structured_chat_html(
            "\n".join(
                [
                    "responder: Lyra",
                    "observation: Something changed",
                    "proposal: Ship the fix",
                    "handoff question to Noctis: What do you think?",
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
        self.assertIn("紬 | TURN", html)
        self.assertNotIn("·", html)

    def test_autochat_helpers(self) -> None:
        self.assertEqual(cli.autochat_job_name(1), "shared-board-autochat-001")
        self.assertEqual(cli.autochat_cron_expression(1, 2), "5 0-59/6 * * * *")
        self.assertEqual(cli.autochat_cron_expression(2, 2), "5 2-59/6 * * * *")
        self.assertEqual(cli.autochat_cron_expression(3, 2), "5 4-59/6 * * * *")
        self.assertEqual(cli.previous_speaker(1), "noctis")
        self.assertEqual(cli.previous_speaker(2), "aster")
        self.assertEqual(cli.previous_speaker(3), "lyra")

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
                    publish_host="127.0.0.1",
                    gateway_bind="lan",
                    userns="keep-id",
                    config_dir=Path("D:/tmp/instances/agent_002"),
                    workspace_dir=Path("D:/tmp/instances/agent_002/workspace"),
                    gateway_token="token",
                    ollama_base_url="http://127.0.0.1:11434",
                    ollama_model="gemma4:e2b",
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

            expected = {1: "伊織", 2: "紬", 3: "朔"}
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

            self.assertTrue((board_root / "README.md").exists())
            self.assertTrue((board_root / "threads").exists())
            self.assertTrue((board_root / "archive").exists())
            self.assertTrue((board_root / "templates" / "topic-template.md").exists())
            self.assertTrue((board_root / "tools" / "autochat_turn.py").exists())
            self.assertTrue((board_root / "tools" / "render_board_view.py").exists())
            self.assertTrue((board_root / "viewer" / "index.html").exists())

            volume_mounts = manifest["spec"]["containers"][0]["volumeMounts"]
            volumes = manifest["spec"]["volumes"]
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
            self.assertIn("podman.exe kube play", output.getvalue().lower())
            self.assertFalse((temp_root / "instances").exists())


if __name__ == "__main__":
    unittest.main()
