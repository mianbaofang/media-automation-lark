# Release: v0.3.1 - Media Automation Lark

Media Automation Lark v0.3.1 packages the local content-automation workflow as a standard, installable Agent Skill while keeping the repository itself as the source project. The repository's canonical Skill entrypoint is `skills/media-automation-lark/SKILL.md`; the versioned ZIP contains a relocated install entrypoint at `media-automation-lark/SKILL.md`.

## Highlights

- Added the canonical Skill package at `skills/media-automation-lark/`.
- Removed the duplicate repository-root Skill entry so automatic discovery sees one installable package.
- Added a deterministic package builder at `tools/package_skill.py`.
- The versioned install asset is `media-automation-lark-skill-v0.3.1.zip`.
- Its matching SHA-256 file is published with the release asset.
- Added package-structure tests and a clean runtime-file boundary that excludes README media, screenshots, source animation files, MP4 files, and audit reports.
- Aligned the Chinese and English README launch surfaces. Both preview GIFs are 960x540, 5 fps, and 36 seconds.

## Install

Download the versioned Skill ZIP and its checksum from the [v0.3.1 Release](https://github.com/mianbaofang/media-automation-lark/releases/tag/v0.3.1). GitHub's automatic source archive is the repository source tree and is not the supported Skill install asset.

After downloading, verify the checksum and extract the archive. The archive has one top-level directory:

```text
media-automation-lark/
  SKILL.md
  LICENSE
  DISCLAIMER.md
  requirements.txt
  config.json.example
  manifest.json
  agents/
  assets/
  references/
  scripts/
  security/
```

In the source repository, the canonical entrypoint is:

```text
skills/media-automation-lark/SKILL.md
```

After extracting the release ZIP for a Skill library, the install entrypoint is:

```text
media-automation-lark/SKILL.md
```

Install the extracted `media-automation-lark/` directory as one package. Keep all files inside that directory together; the scripts and references are part of the runtime contract.

## Verification

The release verification checklist was run for this release:

- Run Python compilation and the repository test suite.
- Regenerate portable Yao governance and trust evidence with `python tools/generate_yao_reports.py`.
- Validate package structure, including one canonical `SKILL.md`, required support files, no machine-specific paths, and no promotional media in the ZIP.
- Generate deterministic ZIP output and its SHA-256 from the package manifest version.
- Run `git diff --check` and the launch/discovery audits.
- Re-check preview GIF dimensions, frame rate, duration, and file size.

The published release was created only after the local checks passed. A successful local check does not by itself prove search ranking or adoption.

## Runtime Scope

The Skill can collect and organize RSS/API content, public web material, local files, and platform metrics into previewable Markdown, JSON backups, HTML dashboards, and optional Feishu/Lark records. Writes remain explicit and dry-run capable.

`--offline-demo` runs the collector's built-in fixture without network access. `--dry-run` is a separate preview mode: it may read real inputs or public APIs and writes local artifacts, but skips Feishu/Lark writes and bot notifications. The project does not include a resident scheduler; cron, systemd timer, or Windows Task Scheduler must be configured by the user with the templates under `assets/cron-examples/`.

For Bilibili metrics, copy `config.json.example` to `config.json`, set `platforms.bilibili.mid` to a numeric account UID, and pass `--config config.json` explicitly. URL checks reject non-HTTP(S), local, metadata, and literal private or reserved IP targets; ordinary hostnames are not DNS-resolved, so the filter is not a complete SSRF defense.

The project does not bypass logins, captchas, paywalls, encryption, platform controls, or robots.txt restrictions. Read [DISCLAIMER.md](DISCLAIMER.md) before use.

## Asset Policy

The install ZIP and checksum are functional release assets. The README GIFs, screenshots, HyperFrames source, promotional MP4, and audit reports remain repository documentation or production material and are not required to run the Skill.

## Upgrade

This package follows the existing `media-automation-lark` Skill name. Replace an older installed package with the contents of the v0.3.1 ZIP, then run the environment check and the offline demo before enabling network or Feishu/Lark writes.

## Links

- Repository: <https://github.com/mianbaofang/media-automation-lark>
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Canonical repository Skill entrypoint: [`skills/media-automation-lark/SKILL.md`](skills/media-automation-lark/SKILL.md)
- ZIP install entrypoint: `media-automation-lark/SKILL.md`
- License: [LICENSE](LICENSE)
