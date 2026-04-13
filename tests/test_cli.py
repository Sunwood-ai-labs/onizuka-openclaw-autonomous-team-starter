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
            self.assertEqual(values["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL_INSTANCE_001"], "20m")
            self.assertEqual(values["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL_INSTANCE_002"], "10m")
            self.assertEqual(values["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL_INSTANCE_003"], "45m")
            self.assertEqual(values["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL_INSTANCE_004"], "30m")
            self.assertEqual(values["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL_INSTANCE_005"], "15m")
            self.assertEqual(values["OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL_INSTANCE_006"], "60m")

    def test_set_mattermost_autonomy_env_inherits_primary_model_when_blank(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)
            env_file.write_text(
                env_file.read_text(encoding="utf-8") + "OPENCLAW_MODEL_REF=ollama/gemma4:e2b\nOPENCLAW_MATTERMOST_AUTONOMY_MODEL=\n",
                encoding="utf-8",
            )

            cli.set_mattermost_autonomy_env(env_file, enabled=True, interval_minutes=6)
            values = cli.parse_env_file(env_file)

            self.assertEqual(values["OPENCLAW_MATTERMOST_AUTONOMY_MODEL"], "ollama/gemma4:e2b")

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
            self.assertEqual(
                payload["channels"]["mattermost"]["botToken"],
                "${OPENCLAW_MATTERMOST_BOT_TOKEN}",
            )
            self.assertEqual(payload["channels"]["mattermost"]["chatmode"], "oncall")
            self.assertEqual(payload["channels"]["mattermost"]["groups"]["*"]["requireMention"], True)
            self.assertEqual(payload["channels"]["mattermost"]["network"]["dangerouslyAllowPrivateNetwork"], True)
            self.assertEqual(payload["plugins"]["entries"]["mattermost"]["enabled"], True)

    def test_ensure_openclaw_config_does_not_leak_heartbeat_prompt_into_normal_message_turns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)
            env_text = env_file.read_text(encoding="utf-8")
            env_text += "\n".join(
                [
                    "OPENCLAW_MODEL_REF=ollama/gemma4:e2b",
                    "OPENCLAW_MATTERMOST_ENABLED=true",
                    "OPENCLAW_MATTERMOST_BASE_URL=http://mattermost:8065",
                    "OPENCLAW_MATTERMOST_BOT_TOKEN=test-bot-token",
                    "OPENCLAW_MATTERMOST_AUTONOMY_ENABLED=false",
                    "",
                ]
            )
            env_file.write_text(env_text, encoding="utf-8")

            cfg = cli.ensure_state(cli.load_config(env_file))
            payload = json.loads((cfg.config_dir / "openclaw.json").read_text(encoding="utf-8"))

            self.assertNotIn("heartbeat", payload["agents"]["defaults"])
            main_agent = next(entry for entry in payload["agents"]["list"] if entry["id"] == "main")
            self.assertNotIn("heartbeat", main_agent)

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

            self.assertEqual(
                openclaw_payload["channels"]["mattermost"]["botToken"],
                "${OPENCLAW_MATTERMOST_BOT_TOKEN}",
            )
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

    def test_load_runtime_env_merges_state_env_and_control_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            state_env = temp_root / ".env"
            control_env = temp_root / "control.env"
            state_env.write_text("ZAI_API_KEY=test-zai-key\nOPENCLAW_MATTERMOST_BOT_TOKEN=bot-token\n", encoding="utf-8")
            control_env.write_text(
                "OPENCLAW_MODEL_REF=zai/glm-5.1\nOPENCLAW_MATTERMOST_TEAM_NAME=openclaw\nOPENCLAW_MATTERMOST_CHANNEL_NAME=triad-lab\n",
                encoding="utf-8",
            )

            with mock.patch.object(mattermost_common_runtime, "STATE_ENV_PATH", state_env), mock.patch.object(
                mattermost_common_runtime, "CONTROL_ENV_PATH", control_env
            ):
                env = mattermost_common_runtime.load_runtime_env()
                values = mattermost_common_runtime.load_control_values()

            self.assertEqual(env["OPENCLAW_MATTERMOST_BOT_TOKEN"], "bot-token")
            self.assertEqual(values["model_provider"], "zai")
            self.assertEqual(values["model_api_key"], "test-zai-key")
            self.assertEqual(values["team_name"], "openclaw")

    def test_load_mattermost_runtime_resolves_bot_token_from_state_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            state_env = temp_root / ".env"
            control_env = temp_root / "control.env"
            openclaw_config = temp_root / "openclaw.json"

            state_env.write_text("OPENCLAW_MATTERMOST_BOT_TOKEN=bot-token-123\n", encoding="utf-8")
            control_env.write_text("OPENCLAW_MATTERMOST_BASE_URL=http://mattermostverify:8065\n", encoding="utf-8")
            openclaw_config.write_text(
                json.dumps(
                    {
                        "channels": {
                            "mattermost": {
                                "baseUrl": "http://mattermostverify:8065",
                                "botToken": "${OPENCLAW_MATTERMOST_BOT_TOKEN}",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(mattermost_common_runtime, "STATE_ENV_PATH", state_env), mock.patch.object(
                mattermost_common_runtime, "CONTROL_ENV_PATH", control_env
            ), mock.patch.object(mattermost_common_runtime, "OPENCLAW_CONFIG_PATH", openclaw_config):
                base_url, bot_token = mattermost_common_runtime.load_mattermost_runtime()

            self.assertEqual(base_url, "http://mattermostverify:8065")
            self.assertEqual(bot_token, "bot-token-123")

    def test_resolve_bot_ids_ignores_missing_optional_handles(self) -> None:
        def fake_mattermost_request(base_url: str, token: str, path: str, **_: object) -> tuple[int, dict[str, str], object | None]:
            if path.endswith("/iori"):
                return 200, {}, {"id": "bot-iori"}
            raise RuntimeError(f"HTTP 404 {base_url}{path}: not found")

        with mock.patch.object(mattermost_common_runtime, "mattermost_request", side_effect=fake_mattermost_request):
            bot_ids = mattermost_common_runtime.resolve_bot_ids("http://mattermostverify:8065", "token")

        self.assertEqual(bot_ids, {"iori": "bot-iori"})

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

    def test_effective_ollama_base_url_uses_podman_gateway_when_default_alias_fails(self) -> None:
        with mock.patch.object(cli, "podman_machine_gateway_ip", return_value="172.27.208.1"), mock.patch.object(
            cli, "http_endpoint_reachable", return_value=True
        ):
            resolved = cli.effective_ollama_base_url("http://host.containers.internal:11434")

        self.assertEqual(resolved, "http://172.27.208.1:11434")

    def test_raw_env_ollama_runtime_required_detects_per_instance_override(self) -> None:
        self.assertTrue(
            cli.raw_env_ollama_runtime_required(
                {
                    "OPENCLAW_MODEL_REF": "zai/glm-5.1",
                    "OPENCLAW_MODEL_REF_INSTANCE_001": "ollama/gemma4:e2b",
                }
            )
        )

    def test_scaled_instance_state_writes_resolved_ollama_base_url_to_control_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)
            env_file.write_text(
                env_file.read_text(encoding="utf-8").replace(
                    "OPENCLAW_OLLAMA_BASE_URL=http://127.0.0.1:11434",
                    "OPENCLAW_OLLAMA_BASE_URL=http://host.containers.internal:11434",
                ),
                encoding="utf-8",
            )

            with mock.patch.object(cli, "podman_machine_gateway_ip", return_value="172.27.208.1"), mock.patch.object(
                cli, "http_endpoint_reachable", return_value=True
            ):
                resolved = cli.ensure_scaled_instance_state(cli.scaled_instance(env_file, 1))

            control_env_text = resolved.config.env_file.read_text(encoding="utf-8")
            self.assertIn("OPENCLAW_OLLAMA_BASE_URL=http://172.27.208.1:11434", control_env_text)

    def test_cmd_doctor_accepts_scaled_instances_without_single_instance_gateway_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            env_file = temp_root / ".env"
            write_env_file(env_file)
            cli.ensure_scaled_instance_state(cli.scaled_instance(env_file, 1))

            args = argparse.Namespace(env_file=env_file)
            output = io.StringIO()
            with redirect_stdout(output), mock.patch.object(cli, "command_exists", return_value=True), mock.patch.object(
                cli, "podman_available", return_value=True
            ), mock.patch.object(cli, "http_endpoint_reachable", return_value=True):
                exit_code = cli.cmd_doctor(args)

            self.assertEqual(exit_code, 0)
            self.assertIn("[ok] scaled instances: 1 under", output.getvalue())
            self.assertIn("[ok] gateway token: managed per scaled instance", output.getvalue())

    def test_mattermost_smoke_reply_has_error_detects_llm_failure(self) -> None:
        self.assertTrue(cli.mattermost_smoke_reply_has_error("LLM request failed: network connection error."))
        self.assertFalse(cli.mattermost_smoke_reply_has_error("Mattermost is working and I am here."))

    def test_cmd_mattermost_smoke_fails_on_error_reply(self) -> None:
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
            raw_env={
                "OPENCLAW_MATTERMOST_OPERATOR_USERNAME": "operator",
                "OPENCLAW_MATTERMOST_TEAM_NAME": "openclaw",
                "OPENCLAW_MATTERMOST_CHANNEL_NAME": "triad-lab",
            },
        )

        def fake_api_request(
            _cfg: cli.MattermostConfig,
            path: str,
            method: str = "GET",
            token: str | None = None,
            payload: dict[str, object] | None = None,
        ) -> tuple[int, dict[str, str], object | None]:
            if path == "/api/v4/users/username/iori":
                return 200, {}, {"id": "user-1"}
            if path == "/api/v4/posts" and method == "POST":
                return 201, {}, {"id": "root-post"}
            if path == "/api/v4/channels/channel-1/posts?page=0&per_page=100":
                return 200, {}, {
                    "posts": {
                        "reply-1": {
                            "root_id": "root-post",
                            "user_id": "user-1",
                            "message": "LLM request failed: network connection error.",
                        }
                    }
                }
            raise AssertionError(f"Unexpected path {path} method={method} payload={payload} token={token}")

        args = argparse.Namespace(env_file=Path("D:/tmp/.env"), count=1, timeout=5)
        with mock.patch.object(cli, "load_mattermost_config", return_value=cfg), mock.patch.object(
            cli, "container_running", return_value=True
        ), mock.patch.object(cli, "wait_for_mattermost_ready"), mock.patch.object(
            cli, "mattermost_state_values", return_value={cli.MATTERMOST_OPERATOR_PASSWORD_KEY: "operator-password"}
        ), mock.patch.object(cli, "mattermost_login", return_value="operator-token"), mock.patch.object(
            cli, "mattermost_mmctl_json", return_value={"id": "channel-1"}
        ), mock.patch.object(cli, "mattermost_api_request", side_effect=fake_api_request):
            with self.assertRaisesRegex(SystemExit, "Mattermost smoke received error replies"):
                cli.cmd_mattermost_smoke(args)

    def test_cmd_mattermost_smoke_posts_one_root_per_requested_bot(self) -> None:
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
            raw_env={
                "OPENCLAW_MATTERMOST_OPERATOR_USERNAME": "operator",
                "OPENCLAW_MATTERMOST_TEAM_NAME": "openclaw",
                "OPENCLAW_MATTERMOST_CHANNEL_NAME": "triad-lab",
            },
        )
        posted_messages: list[str] = []

        def fake_api_request(
            _cfg: cli.MattermostConfig,
            path: str,
            method: str = "GET",
            token: str | None = None,
            payload: dict[str, object] | None = None,
        ) -> tuple[int, dict[str, str], object | None]:
            if path == "/api/v4/users/username/iori":
                return 200, {}, {"id": "user-1"}
            if path == "/api/v4/users/username/tsumugi":
                return 200, {}, {"id": "user-2"}
            if path == "/api/v4/posts" and method == "POST":
                assert payload is not None
                posted_messages.append(str(payload["message"]))
                if "@iori" in str(payload["message"]):
                    return 201, {}, {"id": "root-1"}
                if "@tsumugi" in str(payload["message"]):
                    return 201, {}, {"id": "root-2"}
            if path == "/api/v4/channels/channel-1/posts?page=0&per_page=100":
                return 200, {}, {
                    "posts": {
                        "reply-1": {"root_id": "root-1", "user_id": "user-1", "message": "Iori online."},
                        "reply-2": {"root_id": "root-2", "user_id": "user-2", "message": "Tsumugi online."},
                    }
                }
            raise AssertionError(f"Unexpected path {path} method={method} payload={payload} token={token}")

        args = argparse.Namespace(env_file=Path("D:/tmp/.env"), count=2, timeout=5)
        output = io.StringIO()
        with redirect_stdout(output), mock.patch.object(cli, "load_mattermost_config", return_value=cfg), mock.patch.object(
            cli, "container_running", return_value=True
        ), mock.patch.object(cli, "wait_for_mattermost_ready"), mock.patch.object(
            cli, "mattermost_state_values", return_value={cli.MATTERMOST_OPERATOR_PASSWORD_KEY: "operator-password"}
        ), mock.patch.object(cli, "mattermost_login", return_value="operator-token"), mock.patch.object(
            cli, "mattermost_mmctl_json", return_value={"id": "channel-1"}
        ), mock.patch.object(cli, "mattermost_api_request", side_effect=fake_api_request):
            exit_code = cli.cmd_mattermost_smoke(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(posted_messages), 2)
        self.assertTrue(any(message.startswith("@iori smoke-test") for message in posted_messages))
        self.assertTrue(any(message.startswith("@tsumugi smoke-test") for message in posted_messages))

    def test_cmd_mattermost_smoke_fails_when_requested_bot_is_missing(self) -> None:
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
            raw_env={
                "OPENCLAW_MATTERMOST_OPERATOR_USERNAME": "operator",
                "OPENCLAW_MATTERMOST_TEAM_NAME": "openclaw",
                "OPENCLAW_MATTERMOST_CHANNEL_NAME": "triad-lab",
            },
        )

        def fake_api_request(
            _cfg: cli.MattermostConfig,
            path: str,
            method: str = "GET",
            token: str | None = None,
            payload: dict[str, object] | None = None,
        ) -> tuple[int, dict[str, str], object | None]:
            if path == "/api/v4/users/username/iori":
                return 200, {}, {"id": "user-1"}
            if path == "/api/v4/users/username/tsumugi":
                return 200, {}, {}
            raise AssertionError(f"Unexpected path {path} method={method} payload={payload} token={token}")

        args = argparse.Namespace(env_file=Path("D:/tmp/.env"), count=2, timeout=5)
        with mock.patch.object(cli, "load_mattermost_config", return_value=cfg), mock.patch.object(
            cli, "container_running", return_value=True
        ), mock.patch.object(cli, "wait_for_mattermost_ready"), mock.patch.object(
            cli, "mattermost_state_values", return_value={cli.MATTERMOST_OPERATOR_PASSWORD_KEY: "operator-password"}
        ), mock.patch.object(cli, "mattermost_login", return_value="operator-token"), mock.patch.object(
            cli, "mattermost_mmctl_json", return_value={"id": "channel-1"}
        ), mock.patch.object(cli, "mattermost_api_request", side_effect=fake_api_request):
            with self.assertRaisesRegex(SystemExit, "could not resolve bot users"):
                cli.cmd_mattermost_smoke(args)

    def test_run_mattermost_lounge_turn_now_retries_after_pairing_required(self) -> None:
        instance = self.build_instance()
        completed = [
            mock.Mock(returncode=1, stdout="", stderr="gateway connect failed: GatewayClientRequestError: pairing required"),
            mock.Mock(returncode=0, stdout='{"requestId":"req-1"}', stderr=""),
            mock.Mock(returncode=0, stdout='{"ok":true}', stderr=""),
        ]
        with mock.patch.object(cli.subprocess, "run", side_effect=completed):
            result = cli.run_mattermost_lounge_turn_now(instance, timeout_seconds=30)

        self.assertEqual(result, "queued")

    def test_run_mattermost_lounge_turn_now_falls_back_to_local_agent_after_gateway_failure(self) -> None:
        instance = self.build_instance()
        completed = [
            mock.Mock(returncode=1, stdout="", stderr="gateway closed (1006 abnormal closure (no close frame)): no close reason"),
        ]
        with mock.patch.object(cli.subprocess, "run", side_effect=completed), mock.patch.object(
            cli,
            "run_pod_local_agent",
            return_value={"payloads": [{"text": "POSTED abc123", "mediaUrl": None}]},
        ), mock.patch.object(cli, "main_agent_heartbeat", return_value={"prompt": cli.DEFAULT_HEARTBEAT_PROMPT}):
            result = cli.run_mattermost_lounge_turn_now(instance, timeout_seconds=30)

        self.assertEqual(result, "POSTED abc123")

    def test_cmd_mattermost_lounge_run_now_fails_when_no_new_posts_observed(self) -> None:
        args = argparse.Namespace(env_file=Path("D:/tmp/.env"), count=2, timeout_ms=30000, wait_seconds=0)
        with mock.patch.object(cli, "ensure_env_file"), mock.patch.object(
            cli, "truthy_env", return_value=True
        ), mock.patch.object(
            cli, "parse_env_file", return_value={"OPENCLAW_MATTERMOST_AUTONOMY_ENABLED": "true"}
        ), mock.patch.object(
            cli, "ensure_scaled_instance_state", side_effect=[self.build_instance(), self.build_instance(), self.build_instance()]
        ), mock.patch.object(
            cli, "scaled_instance", return_value=self.build_instance()
        ), mock.patch.object(
            cli, "container_running", return_value=True
        ), mock.patch.object(
            cli, "run_mattermost_lounge_turn_now", return_value="queued"
        ), mock.patch.object(
            cli,
            "pod_local_mattermost_state",
            side_effect=[
                {"channels": [{"threads": [{"last_post_id": "post-1", "root_post_id": "post-1", "last_handle": "iori", "root_preview": "before"}]}]},
                {"channels": [{"threads": [{"last_post_id": "post-1", "root_post_id": "post-1", "last_handle": "iori", "root_preview": "before"}]}]},
            ],
        ), mock.patch.object(
            cli,
            "load_mattermost_config",
            return_value=cli.MattermostConfig(
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
            ),
        ):
            with self.assertRaisesRegex(SystemExit, "produced no new channel activity"):
                cli.cmd_mattermost_lounge_run_now(args)

    def test_cmd_mattermost_lounge_run_now_prints_new_posts(self) -> None:
        args = argparse.Namespace(env_file=Path("D:/tmp/.env"), count=2, timeout_ms=30000, wait_seconds=0)
        output = io.StringIO()
        with redirect_stdout(output), mock.patch.object(cli, "ensure_env_file"), mock.patch.object(
            cli, "truthy_env", return_value=True
        ), mock.patch.object(
            cli, "parse_env_file", return_value={"OPENCLAW_MATTERMOST_AUTONOMY_ENABLED": "true"}
        ), mock.patch.object(
            cli, "ensure_scaled_instance_state", side_effect=[self.build_instance(), self.build_instance(), self.build_instance()]
        ), mock.patch.object(
            cli, "scaled_instance", return_value=self.build_instance()
        ), mock.patch.object(
            cli, "container_running", return_value=True
        ), mock.patch.object(
            cli, "run_mattermost_lounge_turn_now", return_value="queued"
        ), mock.patch.object(
            cli,
            "pod_local_mattermost_state",
            side_effect=[
                {"channels": [{"threads": [{"last_post_id": "post-1", "root_post_id": "post-1", "last_handle": "iori", "root_preview": "before"}]}]},
                {"channels": [{"threads": [{"last_post_id": "post-2", "root_post_id": "post-1", "last_handle": "iori", "root_preview": "new activity"}]}]},
            ],
        ), mock.patch.object(
            cli,
            "load_mattermost_config",
            return_value=cli.MattermostConfig(
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
            ),
        ):
            exit_code = cli.cmd_mattermost_lounge_run_now(args)

        self.assertEqual(exit_code, 0)
        self.assertIn("iori: new activity", output.getvalue())

    def test_cmd_mattermost_lounge_status_uses_pod_local_state(self) -> None:
        args = argparse.Namespace(env_file=Path("D:/tmp/.env"), count=2)
        output = io.StringIO()
        with redirect_stdout(output), mock.patch.object(cli, "ensure_env_file"), mock.patch.object(
            cli, "parse_env_file", return_value={"OPENCLAW_MATTERMOST_AUTONOMY_ENABLED": "true", "OPENCLAW_MATTERMOST_AUTONOMY_INTERVAL": "6m"}
        ), mock.patch.object(
            cli, "ensure_scaled_instance_state", side_effect=[self.build_instance(), self.build_instance()]
        ), mock.patch.object(
            cli, "scaled_instance", return_value=self.build_instance()
        ), mock.patch.object(
            cli, "container_running", return_value=True
        ), mock.patch.object(
            cli, "main_agent_heartbeat", return_value={"every": "10m"}
        ), mock.patch.object(
            cli, "autochat_job", return_value=None
        ), mock.patch.object(
            cli, "mattermost_lounge_job", return_value=None
        ), mock.patch.object(
            cli,
            "pod_local_mattermost_state",
            return_value={"channels": [{"threads": [{"last_post_id": "post-2", "root_post_id": "post-1", "last_handle": "saku", "root_preview": "autonomy post"}]}]},
        ), mock.patch.object(
            cli,
            "load_mattermost_config",
            return_value=cli.MattermostConfig(
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
            ),
        ):
            exit_code = cli.cmd_mattermost_lounge_status(args)

        self.assertEqual(exit_code, 0)
        self.assertIn("saku: autonomy post", output.getvalue())

    def test_refresh_scaled_instances_after_mattermost_seed_reloads_running_instances(self) -> None:
        fake_instances = [self.build_instance()]
        with mock.patch.object(cli, "parse_env_file", return_value={}), mock.patch.object(
            cli, "existing_scaled_instance_ids", return_value=[1]
        ), mock.patch.object(cli, "scaled_instance", return_value=self.build_instance()), mock.patch.object(
            cli, "ensure_scaled_instance_state", side_effect=fake_instances
        ), mock.patch.object(cli, "container_running", return_value=True), mock.patch.object(
            cli, "build_kube_play_command", return_value=["podman", "kube", "play"]
        ), mock.patch.object(cli, "run_process", return_value=0) as run_process_mock:
            refreshed = cli.refresh_scaled_instances_after_mattermost_seed(Path("D:/tmp/.env"))

        self.assertEqual(len(refreshed), 1)
        run_process_mock.assert_called_once()

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
