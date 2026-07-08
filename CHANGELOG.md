# Changelog

## Unreleased

### Added

- Agent-launchable local browser control panel: `scripts/panel-agent.py` opens `http://127.0.0.1:8787` for environment checks, a safe sample run, webpage/file intake, topic-based public search collection, RSS dry-run, dashboard preview, and Feishu opt-in writes.
- Polished the panel into a browser workbench with a plain-language six-task flow, source/ranking controls for search collection, folded internal execution details, and next-step prompts after each run.

## v0.1.0 - 2026-07-07

First public-ready release of Media Automation Lark.

### Added

- Four runnable local workflows: content archiving, search collection, material management, and metrics dashboard generation.
- Feishu/Lark write paths through `lark-cli` for Bitable, Docs, and bot notifications.
- Runtime detection for optional search/fetch backends, with built-in HTTP fallback.
- Root `config.json.example` that keeps secrets behind environment-variable placeholders.
- Bilingual README, disclaimer, release draft, changelog, contribution guide, security policy, and GitHub issue/PR templates.
- MIT license for consistency with the other public repositories.
- HyperFrames product promo source, MiniMax background music, desktop MP4 export, and lightweight README demo GIF.

### Improved

- RSS/API URL entry points now reject unsafe local, private-network, metadata, and non-HTTP(S) targets.
- `data-collector.py --platform` now limits automatic platform fetching to the requested platform.
- Setup docs now point generated config files to the project root.
- Local secrets, runtime outputs, caches, and editor files are excluded by `.gitignore`.

### Fixed

- Corrected the Tavily CLI installation URL shown by the optional backend installer.
- Replaced token-like placeholder text in the Windows Task Scheduler example.

### Known Limitations

- Public platform endpoints may change or rate-limit access. Use `--source` imports when automatic fetching fails.
- Live Feishu/Lark writes require local `lark-cli` login, matching table fields, and user-managed permissions.
- Public release uses the MIT license. The crawler/web-fetching disclaimer still applies.
