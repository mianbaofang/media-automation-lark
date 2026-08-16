#!/usr/bin/env python3
"""Build a deterministic installable ZIP for Media Automation Lark."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path


PACKAGE_NAME = "media-automation-lark"
PACKAGE_RELATIVE = Path("skills") / PACKAGE_NAME
REQUIRED_FILES = (
    "SKILL.md",
    "LICENSE",
    "DISCLAIMER.md",
    "manifest.json",
    "requirements.txt",
    "config.json.example",
    "agents/interface.yaml",
    "agents/openai.yaml",
    "references/api-integration.md",
    "references/lark-cli-setup.md",
    "references/llm-prompt-templates.md",
    "references/renhua-style.md",
    "references/search-backends.md",
    "references/workflow.md",
    "assets/cron-examples/crontab.txt",
    "assets/cron-examples/systemd-timer.md",
    "assets/cron-examples/windows-task-scheduler.md",
    "scripts/collector.py",
    "scripts/common.py",
    "scripts/content-archiver.py",
    "scripts/data-collector.py",
    "scripts/env-check.py",
    "scripts/file2md.py",
    "scripts/gui-panel.py",
    "scripts/install_backends.py",
    "scripts/material-manager.py",
    "scripts/panel-agent.py",
    "scripts/platforms_fetcher.py",
    "scripts/search_backends.py",
    "security/network_policy.json",
    "security/permission_policy.json",
)
# These files document the repository's production output contract. They are
# required for source validation but live outside the installable package.
REQUIRED_SOURCE_EVIDENCE_FILES = (
    "evals/output/schema.json",
    "evals/output/cases.jsonl",
    "evals/semantic_config.json",
    "evals/trigger_cases.json",
)
EXCLUDED_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "output",
    "output_panel",
    "evals",
    "reports",
    "hyperframes",
    "mp4",
    "media",
}
EXCLUDED_RELATIVE_DIRS = {("evals", "output")}
MANIFEST_EXCLUDED_PATHS = {"output", "output_panel", "evals", "reports", "hyperframes", "mp4", "media", "evals/output"}
FORBIDDEN_SUFFIXES = {".gif", ".mp4", ".webm", ".png", ".jpg", ".jpeg", ".zip", ".sha256"}
SENSITIVE_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".jks", ".keystore"}
SENSITIVE_STEMS = {
    "api_key",
    "apikey",
    "credential",
    "credentials",
    "id_rsa",
    "private_key",
    "secret",
    "secrets",
    "service_account",
    "service-account",
}
PRIVATE_PATH = re.compile(r"(?:[A-Za-z]:/)(?:Users|Object)(?:/|$)|/(?:Users|home)(?:/|$)", re.IGNORECASE)


def _casefold_parts(relative: Path) -> tuple[str, ...]:
    return tuple(part.casefold() for part in relative.parts if part not in {"", "."})


def _is_excluded_relative(relative: Path) -> bool:
    parts = _casefold_parts(relative)
    return any(part in EXCLUDED_DIRS for part in parts) or any(
        parts[index : index + len(excluded)] == excluded
        for excluded in EXCLUDED_RELATIVE_DIRS
        for index in range(max(0, len(parts) - len(excluded) + 1))
    )


def _iter_source_files(skill_root: Path):
    """Walk source files while pruning non-package trees before descending."""
    for directory, dirnames, filenames in os.walk(skill_root, topdown=True):
        current = Path(directory)
        relative_dir = current.relative_to(skill_root)
        kept_dirs = []
        for dirname in dirnames:
            child = current / dirname
            if child.is_symlink() or _is_excluded_relative(relative_dir / dirname):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = sorted(kept_dirs, key=lambda value: (value.casefold(), value))
        for filename in sorted(filenames, key=lambda value: (value.casefold(), value)):
            path = current / filename
            if path.is_symlink() or not path.is_file():
                continue
            yield path, path.relative_to(skill_root)


def content_has_private_path(content: str) -> bool:
    """Detect local Windows/POSIX paths, including JSON-escaped strings."""
    candidates = {content, content.replace("\\\\", "\\"), content.replace("\\", "/")}
    try:
        decoded = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        decoded = None

    def strings(value: object):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)

    if decoded is not None:
        candidates.update(strings(decoded))

    return any(
        isinstance(candidate, str)
        and PRIVATE_PATH.search(re.sub(r"[\\/]+", "/", candidate))
        for candidate in candidates
    )


def source_timestamp() -> tuple[int, int, int, int, int, int]:
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "315532800"))
    value = dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc)
    return value.year, value.month, value.day, value.hour, value.minute, value.second


def is_readme(relative: Path) -> bool:
    return relative.name.casefold() == "readme" or relative.name.casefold().startswith(("readme.", "readme-", "readme_"))


def sensitive_reason(relative: Path) -> str | None:
    name = relative.name.casefold()
    if name == "config.json":
        return "runtime config"
    if name == ".env" or name.startswith(".env."):
        return "environment file"
    if relative.suffix.casefold() in SENSITIVE_SUFFIXES:
        return "private key or credential container"
    if relative.stem.casefold() in SENSITIVE_STEMS:
        return "credential-like filename"
    return None


def package_files(skill_root: Path) -> list[tuple[Path, Path]]:
    files: list[tuple[Path, Path]] = []
    for path, relative in _iter_source_files(skill_root):
        if is_readme(relative) or sensitive_reason(relative) or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            continue
        files.append((path, relative))
    return sorted(files, key=lambda item: item[1].as_posix().casefold())


def _normalise_archive_relative(relative: Path) -> str:
    raw = str(relative).replace("\\", "/")
    if not raw or raw in {".", "/"}:
        raise ValueError("archive member path must not be empty or current directory")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise ValueError(f"archive member path must be relative: {raw}")
    normalised = re.sub(r"/+", "/", raw)
    if normalised.startswith("/") or not normalised or normalised == ".":
        raise ValueError(f"invalid archive member path: {raw}")
    parts = normalised.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"invalid archive member path: {raw}")
    return "/".join(parts)


def _archive_entries(files: list[tuple[Path, Path]]) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    seen: dict[str, str] = {}
    root_skill_paths: list[str] = []
    for path, relative in files:
        normalised = _normalise_archive_relative(relative)
        key = normalised.casefold()
        if key in seen:
            raise ValueError(
                f"duplicate archive member after normalization: {seen[key]} and {normalised}"
            )
        seen[key] = normalised
        if normalised.casefold() == "skill.md" or normalised.casefold().endswith("/skill.md"):
            root_skill_paths.append(normalised)
        entries.append((path, f"{PACKAGE_NAME}/{normalised}"))

    if root_skill_paths != ["SKILL.md"]:
        if not root_skill_paths:
            raise ValueError("archive must contain exactly one root-level SKILL.md")
        raise ValueError(
            "archive must contain exactly one root-level SKILL.md; found "
            + ", ".join(root_skill_paths)
        )
    return sorted(entries, key=lambda item: item[1].casefold())


def validate(root: Path, skill_root: Path, files: list[tuple[Path, Path]]) -> list[str]:
    failures: list[str] = []
    for relative in REQUIRED_FILES:
        if not (skill_root / relative).is_file():
            failures.append(f"missing required file: {relative}")
    for relative in REQUIRED_SOURCE_EVIDENCE_FILES:
        if not (root / relative).is_file():
            failures.append(f"missing required source evidence: {relative}")

    try:
        manifest = json.loads((skill_root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"invalid manifest.json: {exc}")
    else:
        if manifest.get("name") != PACKAGE_NAME:
            failures.append("manifest name must match package name")
        if manifest.get("canonical_path") != str(PACKAGE_RELATIVE).replace("\\", "/"):
            failures.append("manifest canonical_path must point to the packaged Skill")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(manifest.get("version") or "")):
            failures.append("manifest version must be semantic")
        evidence_components = {str(value).casefold() for value in (manifest.get("evidence_components") or [])}
        if "source-repo/evals" not in evidence_components:
            failures.append("manifest must declare source-repo/evals as evidence")
        if "source-repo/reports/skill-evidence" not in evidence_components:
            failures.append("manifest must declare source-repo/reports/skill-evidence as evidence")
        if "output eval fixtures" not in (manifest.get("archive_excludes") or []):
            failures.append("manifest must exclude output eval fixtures from the archive")
        package_scope = str(manifest.get("package_scope") or "").casefold()
        if "evals/" not in package_scope or "reports/skill-evidence/" not in package_scope:
            failures.append("manifest package_scope must describe source evidence outside the package")
        declared_excludes = {str(value).casefold() for value in (manifest.get("archive_excludes") or [])}
        for excluded in MANIFEST_EXCLUDED_PATHS:
            if excluded.casefold() not in declared_excludes:
                failures.append(f"manifest must declare archive exclusion: {excluded}")
        for excluded in MANIFEST_EXCLUDED_PATHS:
            if excluded.casefold() not in package_scope:
                failures.append(f"manifest package_scope must describe {excluded}")

    package_skill = skill_root / "SKILL.md"
    if package_skill.is_file():
        package_text = package_skill.read_text(encoding="utf-8")
        package_name = re.search(r"^name:\s*([^\s]+)", package_text, re.MULTILINE)
        if not package_name or package_name.group(1) != PACKAGE_NAME:
            failures.append("packaged SKILL.md must use the canonical name")

    if skill_root.is_dir():
        for path, relative in _iter_source_files(skill_root):
            reason = sensitive_reason(relative)
            if reason:
                failures.append(f"refusing {reason}: {relative.as_posix()}")

    # Output-eval cases remain public source evidence even though they are not
    # packaged. Keep them portable so the repository can be cloned elsewhere.
    for relative in REQUIRED_SOURCE_EVIDENCE_FILES:
        path = root / relative
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if content_has_private_path(content):
            failures.append(f"machine-specific path in source evidence: {relative}")

    try:
        _archive_entries(files)
    except ValueError as exc:
        failures.append(str(exc))

    for path, relative in files:
        if tuple(part.casefold() for part in relative.parts[:2]) == ("evals", "output"):
            failures.append(f"output eval evidence leaked into package: {relative.as_posix()}")
        try:
            _normalise_archive_relative(relative)
        except ValueError as exc:
            failures.append(str(exc))
        if PRIVATE_PATH.search(re.sub(r"[\\/]+", "/", relative.as_posix())):
            failures.append(f"invalid package path: {relative.as_posix()}")
        if path.suffix.lower() in {".md", ".json", ".py", ".yaml", ".yml", ".txt"}:
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if content_has_private_path(content):
                failures.append(f"machine-specific path in {relative.as_posix()}")
    return failures


def write_zip(files: list[tuple[Path, Path]], destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    timestamp = source_timestamp()
    entries = _archive_entries(files)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, member_name in entries:
            info = zipfile.ZipInfo(member_name, date_time=timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Package the canonical Media Automation Lark Skill.")
    parser.add_argument("source_dir", nargs="?", default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output",
        default=None,
        help="Output ZIP path; defaults to dist/media-automation-lark-skill-v<manifest.version>.zip",
    )
    args = parser.parse_args()

    root = Path(args.source_dir).resolve()
    skill_root = root / PACKAGE_RELATIVE
    files = package_files(skill_root) if skill_root.is_dir() else []
    failures = validate(root, skill_root, files)
    if failures:
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    manifest = json.loads((skill_root / "manifest.json").read_text(encoding="utf-8"))
    output_name = f"{PACKAGE_NAME}-skill-v{manifest['version']}.zip"
    destination = Path(args.output) if args.output else Path("dist") / output_name
    if not destination.is_absolute():
        destination = root / destination
    digest = write_zip(files, destination)
    checksum = destination.with_suffix(destination.suffix + ".sha256")
    checksum.write_text(f"{digest}  {destination.name}\n", encoding="ascii")
    print(f"Created {destination}")
    print(f"Files {len(files)}")
    print(f"SHA256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
