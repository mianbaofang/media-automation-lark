# Media Automation Lark

![workflow](assets/media-automation-lark-flow.svg)

A local automation toolkit that connects content ingestion, search collection, material analysis, analytics dashboards, and Feishu/Lark archiving. It uses Python scripts to orchestrate RSS/API inputs, optional search backends, file-to-Markdown conversion, LLM extraction, and `lark-cli` writes to Bitable, Docs, and bot notifications.

Please read [DISCLAIMER.md](DISCLAIMER.md) before using this project. This project is for learning and research only. Any crawling, web fetching, or platform data collection must comply with applicable law, platform Terms of Service, and robots.txt.

## Product Preview

![Media Automation Lark demo](assets/media-automation-lark-demo.gif)

The workflow is designed around daily content-ops cost: search, fetch, material intake, metric review, and Feishu/Lark sync are handled as a previewable, dry-runnable, schedulable loop. People keep the judgment work; scripts take the repeated transfer work.

## What It Does

| Workflow | Script | Output |
|---|---|---|
| Content archiving | `scripts/content-archiver.py` | RSS/API content structured into Feishu Bitable |
| Metrics dashboard | `scripts/data-collector.py` | Platform metrics, `dashboard.html`, `metrics.xlsx`, optional Feishu sync |
| Material management | `scripts/material-manager.py` | Articles, images, PDFs, and Office files converted/analyzed and archived to Feishu Docs |
| Search collection | `scripts/collector.py` | Search results fetched, categorized, and saved as Markdown, with optional Feishu archive |

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/env-check.py --gen-config
copy config.json.example config.json
```

Edit `config.json`:

- Feishu/Lark: set `feishu.app_token`, table IDs, and optional `chat_id`.
- LLM: keep `@env:LARK_LLM_API_KEY` and provide `LARK_LLM_API_KEY` in your environment.
- Platforms: set `platforms.bilibili.mid` for Bilibili metrics, or import metrics via `--source`.

Install and authorize `lark-cli` before writing to Feishu:

```bash
npm install -g @larksuite/cli
lark-cli config init
lark-cli auth login --recommend
```

## Offline Demo

Run a no-network, no-Feishu demo to verify Markdown generation and categorization:

```bash
python scripts/collector.py --offline-demo --category-map "AI:LLM,Agent;Product:growth" --output-dir output_demo --no-archive --no-notify --no-polish
```

Then open `output_demo/index.md`.

## Common Commands

```bash
python scripts/env-check.py
python scripts/install_backends.py --interactive
python scripts/content-archiver.py --rss-url "https://example.com/feed.xml" --dry-run
python scripts/collector.py --query "LLM applications" --category-map "AI:LLM,Agent" --dry-run
python scripts/data-collector.py --fetch --platform bilibili --dry-run
python scripts/material-manager.py --file "./report.pdf" --dry-run
python -m pytest tests
```

## Backends

Backends are detected at runtime. Installed backends are used; missing backends are skipped:

- `anysearch`: search + extraction, no key required.
- `tavily`: search + extraction, requires `TAVILY_API_KEY` or `tvly login`.
- `autocli`: reads authenticated browser pages into Markdown.
- `agent-reach` / `multi-search-engine`: interactive mode only.
- `http`: built-in requests + BeautifulSoup fallback.

See [references/search-backends.md](references/search-backends.md).

## Safety

- URL inputs are filtered by `common.is_safe_url` to block `file://`, localhost, link-local, cloud metadata, and private-network addresses.
- Secrets are read from environment variables or `@env:` placeholders. `config.json` and `.env` are ignored by Git.
- Feishu writes support `--dry-run`; use it first.
- Captured article bodies are preserved by default. Only generated summaries, index text, and notifications are polished.
- The project is not intended to bypass captchas, paywalls, logins, encryption, or platform anti-abuse systems.

## Acknowledgements

This project builds on the following open-source projects and tool ecosystems:

- Python data and parsing ecosystem: `requests`, `feedparser`, `beautifulsoup4`, `pandas`, `openpyxl`, `python-docx`, and `PyPDF2`.
- File-to-Markdown conversion: Microsoft [`markitdown`](https://github.com/microsoft/markitdown).
- Optional search / fetch backends: [`anysearch-skill`](https://github.com/anysearch-ai/anysearch-skill), [`AutoCLI`](https://github.com/nashsu/AutoCLI), and [`Agent-Reach`](https://github.com/Panniantong/Agent-Reach).
- Optional search services and toolchains: Tavily CLI / API, Feishu/Lark Open Platform, and `@larksuite/cli`.
- Demo video pipeline: HyperFrames timeline animation and MiniMax CLI background music generation.

## Release Materials

- Chinese README: `README.md`
- Disclaimer: `DISCLAIMER.md`
- Release notes: `RELEASE.md`
- Changelog: `CHANGELOG.md`
- Contributing guide: `CONTRIBUTING.md`
- Security policy: `SECURITY.md`
- License: `LICENSE`
- Issue / PR templates: `.github/`
- Launch checklist: `reports/github-launch-checklist.md`
- Acknowledgements: see the README section above
- HyperFrames timeline video source: `hyperframes/media-automation-lark-timeline/`
- MiniMax CLI background music: `hyperframes/media-automation-lark-timeline/assets/audio/minimax-bgm.mp3`
- README demo GIF: `assets/media-automation-lark-demo.gif`
- Lightweight workflow animation: `assets/media-automation-lark-flow.svg`
- Static workflow image: `media-automation-skill-workflow.png`

## Status

Prepared as `v0.1.0`. Verification command: `python -m pytest tests`.

The music-backed HyperFrames MP4 has been exported to the Desktop as `media-automation-lark-timeline-music.mp4`.

License: MIT, see [LICENSE](LICENSE).
