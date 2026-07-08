# v0.2.0 - Agent Control Panel for Media Automation Lark

Media Automation Lark v0.2.0 turns the project from a script-first toolkit into an Agent-launchable local workbench. Users can ask an Agent to open the panel, preview results locally, and only write to Feishu/Lark after checking the output.

## New

- Added an Agent-facing panel launcher: `scripts/panel-agent.py start --open` starts the local browser panel and returns `http://127.0.0.1:8787`.
- Added a plain-language local control panel with six tasks: environment check, safe sample run, webpage/file intake, topic search collection, RSS archiving, and dashboard preview.
- Added source-scope and ranking controls for topic collection, including public web, WeChat public pages, Bilibili, Zhihu, Xiaohongshu, Douyin, and custom source filters.
- Added user-facing result summaries for every panel action, with generated files linked directly and internal stdout/stderr folded under "details for Agent debugging".

## Improved

- Search collection now defaults to a fast candidate-index workflow in the panel, so users can inspect results before deciding whether to fetch full pages or write to Feishu.
- README and Skill docs now describe the beginner path: ask an Agent to open the panel instead of asking end users to memorize commands.
- Search result ranking now records public ranking notes in the generated index, so users can see whether ordering came from visible hotness signals, relevance, category match, or author/account match.

## Fixed

- Fixed topic search being blocked by the optional RSS parser dependency when users were not using RSS.
- Fixed Windows subprocess text decoding for search backends by reading tool output as UTF-8 with replacement fallback.

## Verification

- `python -m pytest tests` passed: 20 tests.
- `git diff --check` passed.
- Browser validation covered panel result pages for material intake, empty search input, real topic search, empty RSS input, real RSS dry-run, and dashboard generation.
- The active local panel was verified at `http://127.0.0.1:8787`.

## Known Risks

- Live Feishu/Lark writes still require local `lark-cli` login, matching table fields, and user-managed permissions.
- Public platform search results may be sparse, rate-limited, or noisy. The panel shows a local index first so users can judge quality before deeper collection.
- Search/crawling behavior remains the user's legal responsibility. Read `DISCLAIMER.md` before use.

## Upgrade

For a fresh install:

```bash
pip install -r requirements.txt
python scripts/env-check.py --gen-config
copy config.json.example config.json
python -m pytest tests
```

For non-technical users, ask an Agent to open the Media Automation Lark panel and check the environment first.

## Full Changelog

- https://github.com/mianbaofang/media-automation-lark/compare/v0.1.0...v0.2.0
