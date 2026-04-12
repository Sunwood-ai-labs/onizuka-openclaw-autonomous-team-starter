# Release QA Inventory

## Release Context

- repository: `D:\Prj\openclaw-podman-starter`
- release tag: `v0.1.0`
- compare range: `<none>; initial release mode from root commit f12e84b39ceb8f439a71f07e86739c5f2aa1c584 to tag v0.1.0`
- requested outputs: GitHub release body, docs-backed release notes, companion walkthrough article
- validation commands run: `powershell -ExecutionPolicy Bypass -File D:\Prj\gh-release-notes-skill\scripts\collect-release-context.ps1 -Target main`, `powershell -ExecutionPolicy Bypass -File D:\Prj\gh-release-notes-skill\scripts\verify-svg-assets.ps1 -RepoPath . -Path assets/header.svg,assets/release-header-v0.1.0.svg,docs/public/release-header-v0.1.0.svg`, `uv run python -m compileall src scripts\mattermost_tools`, `uv run python -m unittest discover -s tests`, `uv run openclaw-podman --help`, `npm --prefix docs run docs:build`, `gh release view v0.1.0 --json url,name,body,isDraft,isPrerelease,publishedAt,tagName,targetCommitish`, `gh api repos/Sunwood-ai-labs/onizuka-openclaw-autonomous-team-starter/releases/tags/v0.1.0 --jq ".published_at"`, `git ls-remote --tags origin v0.1.0`
- release URLs: `https://github.com/Sunwood-ai-labs/onizuka-openclaw-autonomous-team-starter/releases/tag/v0.1.0`, `https://sunwood-ai-labs.github.io/onizuka-openclaw-autonomous-team-starter/guide/releases/v0.1.0`, `https://sunwood-ai-labs.github.io/onizuka-openclaw-autonomous-team-starter/guide/articles/v0.1.0-launch`

## Claim Matrix

| claim | code refs | validation refs | docs surfaces touched | scope |
| --- | --- | --- | --- | --- |
| The repo ships a Windows-first starter CLI plus PowerShell wrappers for single-instance and scaled team flows | `src/openclaw_podman_starter/cli.py`, `scripts/init.ps1`, `scripts/launch.ps1`, `scripts/status.ps1`, `scripts/logs.ps1`, `scripts/stop.ps1`, `scripts/print-env.ps1` | `uv run openclaw-podman --help`, `uv run python -m unittest discover -s tests`, `gh-release-notes-skill\scripts\collect-release-context.ps1 -Target main` | `README.md`, `README.ja.md`, `docs/guide/quickstart.md`, `docs/ja/guide/quickstart.md` | steady_state |
| The shipped team loop includes tracked persona scaffolds and a heartbeat-first Mattermost lab | `src/openclaw_podman_starter/cli.py`, `scripts/mattermost.ps1`, `scripts/mattermost_tools/common_runtime.py`, `scripts/mattermost_tools/get_state.py`, `scripts/mattermost_tools/post_message.py`, `scripts/mattermost_tools/create_channel.py`, `scripts/mattermost_tools/add_reaction.py` | `uv run python -m unittest discover -s tests`, `reports/qa-inventory-mattermost-autochat-2026-04-09.md`, `gh-release-notes-skill\scripts\collect-release-context.ps1 -Target main` | `docs/guide/agent-teams.md`, `docs/ja/guide/agent-teams.md`, `docs/guide/validation.md`, `docs/ja/guide/validation.md` | steady_state |
| The docs site now carries versioned release notes, a companion article, and a published release header for v0.1.0 | `docs/.vitepress/config.ts`, `assets/release-header-v0.1.0.svg`, `docs/public/release-header-v0.1.0.svg` | `npm --prefix docs run docs:build`, `gh-release-notes-skill\scripts\verify-svg-assets.ps1 -RepoPath . -Path assets/header.svg,assets/release-header-v0.1.0.svg,docs/public/release-header-v0.1.0.svg`, `https://sunwood-ai-labs.github.io/onizuka-openclaw-autonomous-team-starter/guide/releases/v0.1.0` | `docs/index.md`, `docs/ja/index.md`, `docs/guide/releases/v0.1.0.md`, `docs/ja/guide/releases/v0.1.0.md` | release_collateral |
| The release also ships experimental Rokuseki Mattermost branding bundles and a companion walkthrough article, with README surfaces updated to mention the plugin artifact area | `mattermost-plugins/jp.sunwood.rokuseki-brand/plugin.json`, `mattermost-plugins/jp.sunwood.rokuseki-sidebar-icon/plugin.json`, `reports/rokuseki-channel-plugin.png`, `reports/sidebar-inspect.png` | `gh-release-notes-skill\scripts\collect-release-context.ps1 -Target main`, `https://sunwood-ai-labs.github.io/onizuka-openclaw-autonomous-team-starter/guide/articles/v0.1.0-launch`, `https://sunwood-ai-labs.github.io/onizuka-openclaw-autonomous-team-starter/ja/guide/articles/v0.1.0-launch` | `README.md`, `README.ja.md`, `docs/guide/articles/v0.1.0-launch.md`, `docs/ja/guide/articles/v0.1.0-launch.md` | mixed |

## Steady-State Docs Review

| surface | status | evidence |
| --- | --- | --- |
| README.md | pass | Updated the repository layout section to mention `mattermost-plugins/` so the release note claim about bundled experimental plugins is reflected in steady-state docs |
| README.ja.md | pass | Updated the Japanese repository layout section with the matching `mattermost-plugins/` note |
| docs/index.md | pass | Added latest-release links to the docs-backed release note and companion walkthrough |
| docs/ja/index.md | pass | Added the same latest-release links in the Japanese docs home |
| docs/guide/quickstart.md | pass | Reviewed current startup flow against the release claims; no change needed because the shipped quickstart already matches the release body |
| docs/ja/guide/quickstart.md | pass | Reviewed Japanese quickstart against the release claims; no change needed |
| docs/guide/agent-teams.md | pass | Reviewed heartbeat-first helper and team-loop claims against the current guide; no change needed |
| docs/ja/guide/agent-teams.md | pass | Reviewed the Japanese team guide for the same claims; no change needed |
| docs/guide/configuration.md | pass | Reviewed per-instance autonomy interval and trust-model wording; no change needed for this release |
| docs/ja/guide/configuration.md | pass | Reviewed the Japanese configuration page; no change needed |
| docs/guide/validation.md | pass | Reviewed validation claims against shipped reports and local commands; no change needed |
| docs/ja/guide/validation.md | pass | Reviewed the Japanese validation page; no change needed |
| docs/guide/releases/v0.1.0.md | pass | Created the English docs-backed release note page for the initial release |
| docs/ja/guide/releases/v0.1.0.md | pass | Created the Japanese docs-backed release note page for the initial release |
| docs/guide/articles/v0.1.0-launch.md | pass | Created the English companion walkthrough article |
| docs/ja/guide/articles/v0.1.0-launch.md | pass | Created the Japanese companion walkthrough article |

## QA Inventory

| criterion_id | status | evidence |
| --- | --- | --- |
| compare_range | pass | `powershell -ExecutionPolicy Bypass -File D:\Prj\gh-release-notes-skill\scripts\collect-release-context.ps1 -Target main` reported initial release mode with no previous tag |
| release_claims_backed | pass | Claims are tied to the claim matrix code refs, `git log --reverse --stat --no-merges`, the collector output, and direct file inspection of the current repo surfaces |
| docs_release_notes | pass | `docs/guide/releases/v0.1.0.md, docs/ja/guide/releases/v0.1.0.md` |
| companion_walkthrough | pass | `docs/guide/articles/v0.1.0-launch.md, docs/ja/guide/articles/v0.1.0-launch.md` |
| operator_claims_extracted | pass | Claim matrix completed above for CLI, scaffolds, Mattermost lab, docs publishing, and plugin collateral |
| impl_sensitive_claims_verified | pass | Verified implementation-sensitive claims against `src/openclaw_podman_starter/cli.py`, `scripts/mattermost_tools/common_runtime.py`, `.github/workflows/ci.yml`, `.github/workflows/pages.yml`, and `tests/test_cli.py` |
| steady_state_docs_reviewed | pass | README and primary docs surfaces were reviewed in the table above, with changed files or explicit no-change rationale recorded |
| claim_scope_precise | pass | Release body and docs pages scope the plugin bundles as experimental and state explicitly that `v0.1.0` is an initial release with no previous tag |
| latest_release_links_updated | pass | `docs/.vitepress/config.ts`, `docs/index.md`, and `docs/ja/index.md` now expose release/article navigation and latest-release links |
| svg_assets_validated | pass | `powershell -ExecutionPolicy Bypass -File D:\Prj\gh-release-notes-skill\scripts\verify-svg-assets.ps1 -RepoPath . -Path assets/header.svg,assets/release-header-v0.1.0.svg,docs/public/release-header-v0.1.0.svg` returned `SVG assets look valid.` |
| docs_assets_committed_before_tag | pass | Release collateral was committed in `a73491e Add v0.1.0 release collateral` before the local and remote `v0.1.0` tag was created |
| docs_deployed_live | pass | Pages run `https://github.com/Sunwood-ai-labs/onizuka-openclaw-autonomous-team-starter/actions/runs/24307504048` completed successfully, and the English/Japanese release/article URLs plus the release header SVG returned HTTP 200 |
| tag_local_remote | pass | Local tag `v0.1.0` points at `a73491e`, and `git ls-remote --tags origin v0.1.0` returned `refs/tags/v0.1.0` |
| github_release_verified | pass | `gh release view v0.1.0 --json url,name,body,isDraft,isPrerelease,publishedAt,tagName,targetCommitish` returned the expected public URL and final release body |
| validation_commands_recorded | pass | Validation commands are listed in Release Context and mirrored on `docs/guide/releases/v0.1.0.md` and `docs/ja/guide/releases/v0.1.0.md` |
| publish_date_verified | pass | `gh api repos/Sunwood-ai-labs/onizuka-openclaw-autonomous-team-starter/releases/tags/v0.1.0 --jq ".published_at"` returned `2026-04-12T13:12:36Z` |

## Notes

- blockers: none
- waivers: none
- follow-up docs tasks: review GitHub Actions steps that still emit Node 20 deprecation warnings and decide whether to upgrade to Node 24-compatible action versions in a future maintenance release
