# v0.1.0 - Local Media Automation for Feishu/Lark

Media Automation Lark ships the first public-ready version of the Feishu/Lark media automation workflow: content archiving, analytics, material management, search collection, runtime backend detection, and documentation that makes safe usage explicit.

## New

- Added four runnable workflows: RSS/API content archiving, platform metric dashboards, multimodal material management, and search-to-categorized-Markdown collection.
- Added pluggable search/fetch backend detection for `anysearch`, `tavily`, `autocli`, `agent-reach`, `multi-search-engine`, and built-in HTTP fallback.
- Added Feishu/Lark integration through `lark-cli` for Bitable records, Docs, and bot notifications.
- Added root-level `config.json.example` with env-based secret placeholders.
- Added bilingual README files, acknowledgements, release notes, changelog, contributing guide, security policy, issue/PR templates, launch checklist, and a bilingual disclaimer.
- Added MIT license for public open-source release consistency.
- Added a lightweight README demo GIF derived from the HyperFrames promo video.
- Added an 8-page HyperFrames timeline video source with MiniMax CLI-generated instrumental background music.

## Improved

- Hardened crawler-facing URL inputs in `content-archiver.py` with SSRF filtering for RSS/API URLs.
- Made `data-collector.py --platform` actually limit automatic platform fetching.
- Moved generated config templates to the project root to match setup docs.
- Added `.gitignore` rules for local secrets, runtime outputs, Python caches, and editor noise.
- Corrected the Tavily install URL shown by the backend installer.

## Verification

- `python -m pytest tests` passed: 11 tests.
- `python scripts/collector.py --offline-demo --category-map "AI:大模型,LLM,Agent;产品:增长" --output-dir output_demo --no-archive --no-notify --no-polish` generated a local Markdown demo.
- `python scripts/env-check.py --gen-config` now targets the project root.
- `npx hyperframes lint`, `npx hyperframes validate`, and `npx hyperframes inspect` passed for `hyperframes/media-automation-lark-timeline`.
- `npx hyperframes render --quality high` produced the music-backed MP4; it is attached to the `v0.1.0` GitHub Release. `ffprobe` reported 36.032 seconds.
- `ffmpeg` generated `assets/media-automation-lark-demo.gif` for the README preview.

## Known Risks

- `lark-cli`, Feishu table schemas, and platform API credentials must be configured locally before live writes.
- Bilibili public endpoints may change or rate-limit access; use `--source` imports when platform fetching fails.
- Search/crawling behavior remains the user's legal responsibility. Read `DISCLAIMER.md` before use.
- Public release uses the MIT license. Users must still follow the crawler/web-fetching disclaimer.

## Upgrade

For a fresh install:

```bash
pip install -r requirements.txt
python scripts/env-check.py --gen-config
copy config.json.example config.json
python -m pytest tests
```

Then fill `config.json`, install/auth `lark-cli`, and dry-run one workflow before live use.
