from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock
from contextlib import redirect_stdout
from pathlib import Path

from openclaw_podman_starter import cli

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
MATTERMOST_TOOLS_DIR = SCRIPTS_DIR / "mattermost_tools"
sys.path.insert(0, str(MATTERMOST_TOOLS_DIR))

MATTERMOST_GET_STATE_PATH = MATTERMOST_TOOLS_DIR / "get_state.py"
mattermost_get_state_spec = importlib.util.spec_from_file_location("mattermost_get_state", MATTERMOST_GET_STATE_PATH)
mattermost_get_state = importlib.util.module_from_spec(mattermost_get_state_spec)
assert mattermost_get_state_spec and mattermost_get_state_spec.loader
sys.modules[mattermost_get_state_spec.name] = mattermost_get_state
mattermost_get_state_spec.loader.exec_module(mattermost_get_state)

MATTERMOST_COMMON_RUNTIME_PATH = MATTERMOST_TOOLS_DIR / "common_runtime.py"
mattermost_common_runtime_spec = importlib.util.spec_from_file_location(
    "common_runtime", MATTERMOST_COMMON_RUNTIME_PATH
)
mattermost_common_runtime = importlib.util.module_from_spec(mattermost_common_runtime_spec)
assert mattermost_common_runtime_spec and mattermost_common_runtime_spec.loader
sys.modules[mattermost_common_runtime_spec.name] = mattermost_common_runtime
mattermost_common_runtime_spec.loader.exec_module(mattermost_common_runtime)


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
    def build_instance(self) -> cli.ScaledInstance:
        return cli.ScaledInstance(
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
    def test_run_pod_local_agent_retries_on_rate_limit(self) -> None:
        rate_limited_payload = json.dumps(
            {
                "payloads": [{"text": "⚠️ API rate limit reached. Please try again later.", "mediaUrl": None}],
                "meta": {"stopReason": "error"},
            }
        )
        success_payload = json.dumps(
            {
                "payloads": [{"text": "OK", "mediaUrl": None}],
                "meta": {"stopReason": "stop"},
            }
        )
        completed = [
            mock.Mock(returncode=0, stdout=rate_limited_payload, stderr=""),
            mock.Mock(returncode=0, stdout=success_payload, stderr=""),
        ]

        with mock.patch.object(cli, "podman_bin", return_value="podman"), mock.patch.object(
            cli.subprocess, "run", side_effect=completed
        ) as run_mock, mock.patch.object(cli.time, "sleep") as sleep_mock:
            payload = cli.run_pod_local_agent(self.build_instance(), "hello", 30)

        self.assertEqual(payload["payloads"][0]["text"], "OK")
        self.assertEqual(run_mock.call_count, 2)
        sleep_mock.assert_called_once_with(cli.rate_limit_retry_delay_seconds(1))

    def test_latest_assistant_text_ignores_non_assistant_entries(self) -> None:
        payload = {
            "payloads": [
                {"role": "tool", "text": "tool output"},
                {"role": "assistant", "text": "python3 /tmp/example.py"},
                {"role": "assistant", "text": "POSTED abc123"},
            ]
        }
        self.assertEqual(cli.latest_assistant_text(payload), "POSTED abc123")

    def test_mattermost_get_state_module_exposes_main(self) -> None:
        self.assertTrue(hasattr(mattermost_get_state, "main"))

    def test_scaled_instance_state_seeds_triads_and_mattermost_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)

            expected = {1: "いおり", 2: "つむぎ", 3: "さく"}
            for instance_id, name in expected.items():
                resolved = cli.ensure_scaled_instance_state(cli.scaled_instance(env_file, instance_id))
                soul_path = resolved.config.workspace_dir / "SOUL.md"
                identity_path = resolved.config.workspace_dir / "IDENTITY.md"
                tools_path = resolved.config.workspace_dir / "TOOLS.md"
                mattermost_tools = cli.mattermost_tools_root(resolved)

                self.assertTrue(soul_path.exists())
                self.assertTrue(identity_path.exists())
                self.assertTrue(tools_path.exists())
                self.assertFalse((resolved.config.workspace_dir / "BBS.md").exists())
                self.assertTrue((mattermost_tools / "common_runtime.py").exists())
                self.assertTrue((mattermost_tools / "get_state.py").exists())
                self.assertTrue((mattermost_tools / "post_message.py").exists())
                self.assertTrue((mattermost_tools / "create_channel.py").exists())
                self.assertTrue((mattermost_tools / "add_reaction.py").exists())

                soul_text = soul_path.read_text(encoding="utf-8")
                identity_text = identity_path.read_text(encoding="utf-8")
                tools_text = tools_path.read_text(encoding="utf-8")

                self.assertIn(f"# SOUL.md - {name}", soul_text)
                self.assertIn(f"**名前:** {name}", identity_text)
                self.assertIn(cli.CONTAINER_MATTERMOST_TOOLS_DIR, tools_text)

    def test_scaled_instance_manifest_no_longer_mounts_shared_board(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)

            resolved = cli.ensure_scaled_instance_state(cli.scaled_instance(env_file, 2))
            manifest = json.loads((resolved.config.config_dir / "pod.yaml").read_text(encoding="utf-8"))
            containers = manifest["spec"]["containers"]
            volume_mounts = containers[0]["volumeMounts"]
            volumes = manifest["spec"]["volumes"]

            self.assertEqual(len(containers), 1)
            self.assertEqual(containers[0]["name"], "openclaw-2")
            self.assertEqual(volume_mounts, [{"name": "openclaw-state", "mountPath": cli.CONTAINER_CONFIG_DIR}])
            self.assertEqual(len(volumes), 1)
            self.assertEqual(volumes[0]["name"], "openclaw-state")
            self.assertFalse((resolved.config.config_dir / "board-pod.yaml").exists())

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
            self.assertNotIn("board-pod.yaml", output.getvalue().lower())
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

    def test_set_mattermost_autonomy_env_seeds_persona_intervals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)

            cli.set_mattermost_autonomy_env(env_file, enabled=True, interval_minutes=6)
            values = cli.parse_env_file(env_file)

            self.assertEqual(values["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL"], "6m")
            self.assertEqual(values["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL_INSTANCE_001"], "7m")
            self.assertEqual(values["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL_INSTANCE_002"], "4m")
            self.assertEqual(values["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL_INSTANCE_003"], "10m")
            self.assertEqual(values["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL_INSTANCE_004"], "8m")
            self.assertEqual(values["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL_INSTANCE_005"], "5m")
            self.assertEqual(values["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL_INSTANCE_006"], "12m")

    def test_scaled_instance_applies_autonomy_interval_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)
            env_file.write_text(
                env_file.read_text(encoding="utf-8") + "OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL_INSTANCE_005=5m\n",
                encoding="utf-8",
            )

            instance = cli.scaled_instance(env_file, 5)
            self.assertEqual(instance.config.raw_env["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL"], "5m")

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

    def test_scaled_instance_generated_files_keep_secrets_out_of_tracked_manifest_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)
            env_text = env_file.read_text(encoding="utf-8")
            env_text += "\n".join(
                [
                    "OPENCLAW_MODEL_REF=openrouter/google/gemma-3n-e2b-it:free",
                    "OPENCLAW_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1",
                    "OPENROUTER_API_KEY=test-openrouter-key",
                    "ZAI_API_KEY=test-zai-key",
                    "OPENCLAW_MATTERMOST_ENABLED=true",
                    "OPENCLAW_MATTERMOST_BASE_URL=http://mattermost:8065",
                    "",
                ]
            )
            env_file.write_text(env_text, encoding="utf-8")

            mattermost_root = temp_root / ".openclaw" / "mattermost"
            mattermost_root.mkdir(parents=True)
            (mattermost_root / "state.env").write_text(
                "OPENCLAW_MATTERMOST_BOT_TOKEN_001=mm-token-1\n",
                encoding="utf-8",
            )

            resolved = cli.ensure_scaled_instance_state(cli.scaled_instance(env_file, 1))
            control_env_text = (resolved.config.env_file).read_text(encoding="utf-8")
            state_env_text = (resolved.config.config_dir / ".env").read_text(encoding="utf-8")
            openclaw_payload = json.loads((resolved.config.config_dir / "openclaw.json").read_text(encoding="utf-8"))
            pod_payload = json.loads((resolved.config.config_dir / "pod.yaml").read_text(encoding="utf-8"))

            self.assertNotIn("OPENROUTER_API_KEY=test-openrouter-key", control_env_text)
            self.assertNotIn("ZAI_API_KEY=test-zai-key", control_env_text)
            self.assertNotIn("OPENCLAW_MATTERMOST_BOT_TOKEN=mm-token-1", control_env_text)

            self.assertIn("OPENROUTER_API_KEY=test-openrouter-key", state_env_text)
            self.assertIn("ZAI_API_KEY=test-zai-key", state_env_text)
            self.assertIn("OPENCLAW_MATTERMOST_BOT_TOKEN=mm-token-1", state_env_text)

            self.assertEqual(openclaw_payload["channels"]["mattermost"]["botToken"], "mm-token-1")
            self.assertNotIn("meta", openclaw_payload)

            env_entries = {
                entry["name"]: entry["value"] for entry in pod_payload["spec"]["containers"][0]["env"]
            }
            self.assertEqual(set(env_entries), {"OPENCLAW_GATEWAY_BIND", "TZ"})
            self.assertEqual(env_entries["TZ"], "Asia/Tokyo")

    def test_mattermost_user_id_returns_empty_on_404(self) -> None:
        cfg = cli.MattermostConfig(
            env_file=Path("D:/tmp/.env"),
            root_dir=Path("D:/tmp/.openclaw/mattermost"),
            pod_name="mattermost-pod",
            container_name="mattermost",
            image="image",
            host_port=8065,
            publish_host="127.0.0.1",
            network="podman",
            base_url="http://mattermost:8065",
            raw_env={},
        )
        with mock.patch.object(
            cli,
            "mattermost_api_request",
            side_effect=urllib.error.HTTPError(
                url="http://example.invalid",
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=None,
            ),
        ):
            self.assertEqual(cli.mattermost_user_id(cfg, "iori", "token"), "")

    def test_mattermost_lounge_disable_removes_legacy_autochat(self) -> None:
        args = argparse.Namespace(env_file=Path("D:/tmp/.env"), count=3)

        with mock.patch.object(cli, "ensure_env_file"), mock.patch.object(
            cli, "set_mattermost_autonomy_env"
        ) as set_env_mock, mock.patch.object(
            cli,
            "reconcile_mattermost_autonomy_instances",
            return_value=[self.build_instance()],
        ) as reconcile_mock:
            exit_code = cli.cmd_mattermost_lounge_disable(args)

        self.assertEqual(exit_code, 0)
        set_env_mock.assert_called_once_with(args.env_file, enabled=False)
        reconcile_mock.assert_called_once_with(
            args.env_file,
            [1, 2, 3],
            remove_legacy_cron=True,
            remove_legacy_autochat=True,
        )

    def test_ensure_openclaw_config_supports_openrouter_model_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)
            env_text = env_file.read_text(encoding="utf-8")
            env_text += "\n".join(
                [
                    "OPENCLAW_MODEL_REF=openrouter/google/gemma-3n-e2b-it:free",
                    "OPENCLAW_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1",
                    "OPENROUTER_API_KEY=test-openrouter-key",
                    "",
                ]
            )
            env_file.write_text(env_text, encoding="utf-8")

            cfg = cli.ensure_state(cli.load_config(env_file))
            payload = json.loads((cfg.config_dir / "openclaw.json").read_text(encoding="utf-8"))

            self.assertEqual(payload["agents"]["defaults"]["model"]["primary"], "openrouter/google/gemma-3n-e2b-it:free")
            self.assertEqual(payload["models"]["providers"]["openrouter"]["api"], "openai-completions")
            self.assertEqual(payload["models"]["providers"]["openrouter"]["baseUrl"], "https://openrouter.ai/api/v1")
            self.assertEqual(payload["models"]["providers"]["openrouter"]["apiKey"], "${OPENROUTER_API_KEY}")
            self.assertEqual(payload["models"]["providers"]["openrouter"]["models"][0]["id"], "google/gemma-3n-e2b-it:free")
            self.assertEqual(payload["plugins"]["entries"]["openrouter"]["enabled"], True)
            self.assertNotIn("ollama", payload["models"]["providers"])

    def test_ensure_openclaw_config_supports_zai_glm51_model_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)
            env_text = env_file.read_text(encoding="utf-8")
            env_text += "\n".join(
                [
                    "OPENCLAW_MODEL_REF=zai/glm-5.1",
                    "ZAI_API_KEY=test-zai-key",
                    "",
                ]
            )
            env_file.write_text(env_text, encoding="utf-8")

            cfg = cli.ensure_state(cli.load_config(env_file))
            payload = json.loads((cfg.config_dir / "openclaw.json").read_text(encoding="utf-8"))

            self.assertEqual(payload["agents"]["defaults"]["model"]["primary"], "zai/glm-5.1")
            self.assertEqual(payload["agents"]["defaults"]["model"]["fallbacks"], ["zai/glm-4.7"])
            self.assertEqual(payload["auth"]["cooldowns"]["rateLimitedProfileRotations"], 10)
            self.assertEqual(payload["plugins"]["entries"]["zai"]["enabled"], True)
            self.assertNotIn("models", payload["agents"]["defaults"])
            self.assertNotIn("models", payload)

    def test_ensure_openclaw_config_syncs_managed_agent_models_to_primary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)
            config_dir = temp_root / ".openclaw"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "openclaw.json").write_text(
                json.dumps(
                    {
                        "agents": {
                            "defaults": {"model": {"primary": "ollama/gemma4:e2b"}},
                            "list": [
                                {"id": "main"},
                                {"id": "autochat-aster", "model": "ollama/gemma4:e2b"},
                                {"id": "discuss-aster", "model": "ollama/gemma4:e2b"},
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )
            env_text = env_file.read_text(encoding="utf-8")
            env_text += "\n".join(
                [
                    "OPENCLAW_MODEL_REF=zai/glm-5.1",
                    "ZAI_API_KEY=test-zai-key",
                    "",
                ]
            )
            env_file.write_text(env_text, encoding="utf-8")

            cfg = cli.ensure_state(cli.load_config(env_file))
            payload = json.loads((cfg.config_dir / "openclaw.json").read_text(encoding="utf-8"))
            models = {entry["id"]: entry.get("model") for entry in payload["agents"]["list"]}

            self.assertEqual(models["autochat-aster"], "zai/glm-5.1")
            self.assertEqual(models["discuss-aster"], "zai/glm-5.1")

    def test_mattermost_autochat_runtime_supports_openrouter(self) -> None:
        runtime = mattermost_common_runtime.planner_runtime_from_env(
            {
                "OPENCLAW_MODEL_REF": "openrouter/google/gemma-3n-e2b-it:free",
                "OPENCLAW_OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
                "OPENROUTER_API_KEY": "test-openrouter-key",
            }
        )

        self.assertEqual(runtime["model_provider"], "openrouter")
        self.assertEqual(runtime["model_id"], "google/gemma-3n-e2b-it:free")
        self.assertEqual(runtime["model_base_url"], "https://openrouter.ai/api/v1")
        self.assertEqual(runtime["model_api_key"], "test-openrouter-key")

    def test_mattermost_autochat_runtime_supports_zai(self) -> None:
        runtime = mattermost_common_runtime.planner_runtime_from_env(
            {
                "OPENCLAW_MODEL_REF": "zai/glm-5.1",
                "OPENCLAW_ZAI_BASE_URL": "https://api.z.ai/api/coding/paas/v4",
                "ZAI_API_KEY": "test-zai-key",
            }
        )

        self.assertEqual(runtime["model_provider"], "zai")
        self.assertEqual(runtime["model_id"], "glm-5.1")
        self.assertEqual(runtime["model_base_url"], "https://api.z.ai/api/coding/paas/v4")
        self.assertEqual(runtime["model_api_key"], "test-zai-key")

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
