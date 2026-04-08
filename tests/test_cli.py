from __future__ import annotations

import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from openclaw_podman_starter import cli


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

            expected = {1: "Aster", 2: "Lyra", 3: "Noctis"}
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
                self.assertIn("- ユーザーが英語で話しかけても、翻訳依頼や英語指定がない限り返答は日本語で行う。", soul_text)
                self.assertIn(cli.CONTAINER_SHARED_BOARD_DIR, soul_text)
                self.assertIn(f"**名前:** {name}", identity_text)
                self.assertIn("**返答言語:** 日本語が既定", identity_text)
                self.assertIn("**補足:** 英語で話しかけられても、英語指定がなければ日本語で返す", identity_text)
                self.assertIn(f"# BBS.md - {name} の共有掲示板メモ", bbs_text)
                self.assertIn(cli.CONTAINER_SHARED_BOARD_DIR, bbs_text)
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
