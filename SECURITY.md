# Security Policy

## Supported Versions

`v0.1.x` receives security fixes while this project is actively maintained.

## Reporting A Vulnerability

Please do not publish working exploits, real credentials, private data, or platform-abuse instructions in public issues. Use GitHub Security Advisories when the repository is public, or contact the project owner through the GitHub profile linked from the repository.

Include:

- affected script or workflow
- exact command or configuration shape needed to reproduce
- expected impact
- whether real credentials or private data were involved

## Secrets

The project expects secrets to come from environment variables or `@env:` placeholders. Do not commit:

- `config.json`
- `.env` files
- Feishu/Lark tokens
- LLM or search API keys
- browser session dumps or cookies

## Web Fetching Boundary

Crawler-facing URLs should pass through `common.is_safe_url` or an equivalent guard. New fetch paths must reject local files, localhost, link-local addresses, cloud metadata addresses, and private-network targets by default.

This project is not intended to bypass logins, paywalls, captchas, encryption, platform anti-abuse systems, or access controls.
