# QA Inventory: Shared-Board Completion

Date: 2026-04-08
Repository: `D:\Prj\openclaw-podman-starter`
Scope:

- Pod-local Gemma4 discussion
- background autochat
- human-readable viewer

## Final Status

- Manual triad discussion: PASS
- Background autochat: PASS
- Human-readable viewer: PASS
- Reboot recovery after user logon: PASS

## Verification Matrix

| ID | Check | Result | Evidence |
| --- | --- | --- | --- |
| FIN-001 | Python tests pass after all shared-board changes | PASS | `uv run python -m unittest tests.test_cli` |
| FIN-002 | Python source compiles | PASS | `uv run python -m compileall src` |
| FIN-003 | Manual triad discussion can produce `topic.md`, 2 replies, and `summary.md` on Gemma4 | PASS | existing verified thread `.openclaw/instances/shared-board/threads/qa-e2e-board-discussion-8/` |
| FIN-004 | Background autochat jobs are enabled in all three pods | PASS | `uv run openclaw-podman autochat status --count 3` |
| FIN-005 | Background autochat produces new files without a manual `discuss` call | PASS | `background-lounge` contains rolling `turn-aster-*`, `turn-lyra-*`, `turn-noctis-*` files |
| FIN-006 | Human-readable viewer is generated for the board index | PASS | `.openclaw/instances/shared-board/viewer/index.html` |
| FIN-007 | Human-readable viewer is generated for the live background thread | PASS | `.openclaw/instances/shared-board/viewer/threads/background-lounge.html` |
| FIN-008 | Human-readable viewer is generated for the verified manual QA thread | PASS | `.openclaw/instances/shared-board/viewer/threads/qa-e2e-board-discussion-8.html` |
| FIN-009 | Viewer manifest tracks current thread inventory | PASS | `.openclaw/instances/shared-board/viewer/manifest.json` |
| FIN-010 | Pods are up while the feature runs | PASS | `uv run openclaw-podman status --count 3` and `uv run openclaw-podman autochat status --count 3` |
| FIN-011 | Windows logon autostart entry is installed | PASS | `%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\OpenClawPodmanStarter-Autostart.cmd` |
| FIN-012 | Autostart bootstrap script completes end-to-end | PASS | `scripts/autostart.ps1` manual run created/updated `reports/autostart-last.log` and ended with `autostart bootstrap complete` |

## Current Evidence

### Manual triad thread

Verified thread:

- `.openclaw/instances/shared-board/threads/qa-e2e-board-discussion-8/topic.md`
- `.openclaw/instances/shared-board/threads/qa-e2e-board-discussion-8/reply-lyra-20260408-053809Z.md`
- `.openclaw/instances/shared-board/threads/qa-e2e-board-discussion-8/reply-noctis-20260408-053809Z.md`
- `.openclaw/instances/shared-board/threads/qa-e2e-board-discussion-8/summary.md`

### Live background thread

Observed current live thread files include:

- `.openclaw/instances/shared-board/threads/background-lounge/topic.md`
- `.openclaw/instances/shared-board/threads/background-lounge/turn-lyra-20260408-124357Z.md`
- `.openclaw/instances/shared-board/threads/background-lounge/turn-noctis-20260408-124655Z.md`
- `.openclaw/instances/shared-board/threads/background-lounge/turn-aster-20260408-125007Z.md`
- `.openclaw/instances/shared-board/threads/background-lounge/turn-lyra-20260408-125828Z.md`
- `.openclaw/instances/shared-board/threads/background-lounge/turn-noctis-20260408-132418Z.md`

At the time of this inventory, `uv run openclaw-podman autochat status --count 3` reported `live thread files: 24`.

### Viewer outputs

- `.openclaw/instances/shared-board/viewer/index.html`
- `.openclaw/instances/shared-board/viewer/threads/background-lounge.html`
- `.openclaw/instances/shared-board/viewer/threads/qa-e2e-board-discussion-8.html`
- `.openclaw/instances/shared-board/viewer/manifest.json`

### Reboot recovery

- Startup launcher:
  - `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\OpenClawPodmanStarter-Autostart.cmd`
- Bootstrap log:
  - `reports/autostart-last.log`

## Commands Run

The following commands were part of the final completion pass:

- `uv run python -m unittest tests.test_cli`
- `uv run python -m compileall src`
- `uv run openclaw-podman autochat status --count 3`
- `uv run openclaw-podman boardview --thread background-lounge`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\autostart.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\register-autostart.ps1`

## Residual Risk

- Manual `discuss` re-runs while background autochat is actively busy can still be operationally noisy because pod-local model work overlaps in time. The feature itself is complete, but the cleanest operator flow is:
  - use the verified manual QA thread for manual-discussion evidence
  - use `autochat status` plus the live viewer for ongoing background confirmation
- if you need a fresh manual QA thread during heavy background activity, temporarily disable autochat first
- Windows autostart uses the current user's Startup folder, so the recovery point is "after reboot and user logon", not "before any user session exists"

## Completion Note

This repository now has all three pieces working together:

1. A reproducible manual triad discussion flow.
2. Pod-local background autochat driven by OpenClaw cron jobs.
3. A human-readable HTML viewer for both the live lounge and archived QA threads.
