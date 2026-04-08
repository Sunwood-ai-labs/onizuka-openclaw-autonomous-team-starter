# QA Inventory: Autonomous Gemma4 Board Discussion

Date: 2026-04-08
Repository: `D:\Prj\openclaw-podman-starter`
Verified thread: `qa-e2e-board-discussion-8`

## Goal

Verify that each scaled Podman instance can run pod-local OpenClaw with `ollama/gemma4:e2b`, share one file-backed board, and leave a real discussion trail consisting of:

- `topic.md`
- one reply from つむぎ
- one reply from さく
- `summary.md`

## QA Checklist

| ID | Check | Result | Evidence |
| --- | --- | --- | --- |
| QA-001 | Python unit tests still pass after discussion orchestration changes | PASS | `uv run python -m unittest tests.test_cli` |
| QA-002 | Source still compiles | PASS | `uv run python -m compileall src` |
| QA-003 | Scaled state regenerates shared board scaffold | PASS | `uv run openclaw-podman init --count 3` created `.openclaw/instances/shared-board/README.md`, `threads/`, `archive/`, `templates/` |
| QA-004 | Three scaled pods are running | PASS | `uv run openclaw-podman status --count 3` |
| QA-005 | Shared board is mounted into each pod | PASS | `podman inspect openclaw-1`, `openclaw-2`, `openclaw-3` showed bind mount to `/home/node/.openclaw/shared-board` |
| QA-006 | Pod-local OpenClaw can reach Ollama from inside the pod | PASS | `podman exec openclaw-1 /bin/sh -lc "curl --max-time 5 -sS http://172.27.208.1:11434/api/version"` returned `{"version":"0.20.2"}` |
| QA-007 | Pod-local OpenClaw uses Gemma4 E2B | PASS | `openclaw.json` for agents 1-3 sets primary model to `ollama/gemma4:e2b`; `discuss` output reported `via ollama/gemma4:e2b` for all stages |
| QA-008 | One pod-local agent can write to the shared board | PASS | Manual smoke created `threads/qa-smoke/topic.md` via `openclaw agent --local` inside `openclaw-1` |
| QA-009 | Full triad discussion command completes | PASS | `uv run openclaw-podman discuss --topic "Gemma4 三体の OpenClaw が shared-board 上で自律的に相談し、合意サマリを残せるか QA 観点で確認する" --thread-id qa-e2e-board-discussion-8 --count 3 --starter 1 --timeout 240` exited `0` |
| QA-010 | Board thread contains all expected files | PASS | `.openclaw/instances/shared-board/threads/qa-e2e-board-discussion-8/` contains `topic.md`, `reply-lyra-20260408-053809Z.md`, `reply-noctis-20260408-053809Z.md`, `summary.md` |

## Final Evidence

Thread directory:

- `.openclaw/instances/shared-board/threads/qa-e2e-board-discussion-8/topic.md`
- `.openclaw/instances/shared-board/threads/qa-e2e-board-discussion-8/reply-lyra-20260408-053809Z.md`
- `.openclaw/instances/shared-board/threads/qa-e2e-board-discussion-8/reply-noctis-20260408-053809Z.md`
- `.openclaw/instances/shared-board/threads/qa-e2e-board-discussion-8/summary.md`

Observed `discuss` output:

- `いおり posted topic via ollama/gemma4:e2b`
- `つむぎ posted reply via ollama/gemma4:e2b`
- `さく posted reply via ollama/gemma4:e2b`
- `いおり posted summary via ollama/gemma4:e2b`

## Notes

- Early verification runs exposed three real issues:
  - host-side Windows paths were mistakenly passed into pod-local prompts
  - OpenClaw `--json` output sometimes arrived on `stderr` or with log prefixes
  - the summary stage could return markdown text without writing `summary.md`
- Earlier exploratory threads were moved under `.openclaw/instances/shared-board/archive/` after the final verified run succeeded, so the live `threads/` directory keeps only `qa-e2e-board-discussion-8`.
- The final implementation fixes those issues by:
  - using container-native board paths
  - parsing JSON from either stream
  - isolating each stage into its own OpenClaw session
  - retrying based on actual file creation
  - using a pod-local writeback step for the summary when the model returns summary text before writing the file
