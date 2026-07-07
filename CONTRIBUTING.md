# Contributing

Thanks for helping improve Media Automation Lark. This project is a local automation toolkit, so changes should stay practical, testable, and safe for users running it on their own machines.

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests
```

Use `config.json.example` as the template for local configuration. Do not commit `config.json`, `.env`, logs, exported reports, or real credentials.

## Before Opening a Pull Request

- Keep the change small and tied to one workflow or document.
- Add or update tests when behavior changes.
- Run `python -m pytest tests`.
- Use `--dry-run` when testing scripts that can write to Feishu/Lark.
- Update README, release notes, or examples when a user-facing command changes.

## Web Fetching And Crawling Changes

Changes that touch crawling, search, browser automation, RSS/API fetching, or platform data collection must preserve the project boundary:

- Do not add behavior that bypasses login, paywalls, captchas, encryption, rate limits, or access controls.
- Do not collect private or personal information by default.
- Keep conservative defaults and clear `--dry-run` paths.
- Respect platform Terms of Service, robots.txt, and applicable laws.

If a feature depends on a platform rule or public API that may change, document the fallback path.
