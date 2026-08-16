# GitHub Launch Notes

## Historical v0.1.0 Record

The links and release assets in this section document the historical v0.1.0 publication. They are not the current release checklist or the commands to run for v0.3.0.

- Repository: `https://github.com/mianbaofang/media-automation-lark`
- Release: `https://github.com/mianbaofang/media-automation-lark/releases/tag/v0.1.0`
- Bilingual README: `README.md`, `README.en.md`
- Bilingual crawler/web-fetching disclaimer: `DISCLAIMER.md`
- Release draft: `RELEASE.md`
- Changelog: `CHANGELOG.md`
- Security policy: `SECURITY.md`
- Contributing guide: `CONTRIBUTING.md`
- README acknowledgements for dependencies, optional backends, and video tooling
- MIT license: `LICENSE`
- Issue and pull request templates: `.github/`
- Project audit report: `reports/project-audit.md`
- Lightweight README demo GIF: `assets/media-automation-lark-demo.gif`
- HyperFrames promo source: `hyperframes/media-automation-lark-timeline/`
- Music-backed MP4: attached to the `v0.1.0` GitHub Release
- Tests: `python -m pytest tests`

## v0.3.0 Local Pre-Review

- Status: local release materials prepared for review; not published by this checklist.
- Canonical repository Skill entrypoint: `skills/media-automation-lark/SKILL.md`
- ZIP install entrypoint: `media-automation-lark/SKILL.md` after extracting `media-automation-lark-skill-v0.3.0.zip`
- Chinese README preview asset: `assets/media-automation-lark-demo.gif` (960x540, 5 fps, 36 seconds)
- English README preview asset: `assets/media-automation-lark-demo.en.gif` (960x540, 5 fps, 36 seconds)
- Preview click-through source: `hyperframes/media-automation-lark-timeline/index.html`
- Release draft: `RELEASE.md`
- Package and checksum: `dist/media-automation-lark-skill-v0.3.0.zip` and matching `.zip.sha256`

## Recommended GitHub Repository Settings

- Description: `Local media automation toolkit for Feishu/Lark: content archiving, search collection, material management, and analytics dashboards.`
- Topics: `python`, `feishu`, `lark`, `bitable`, `content-automation`, `media-workflow`, `rss`, `markdown`, `automation`, `dashboard`
- First release title: `v0.1.0 - Local Media Automation for Feishu/Lark`
- Website/social preview: use `assets/media-automation-lark-demo.gif` or `media-automation-skill-workflow.png`

## Historical v0.1.0 Publication Commands

The following commands are retained only as a record of the original v0.1.0 setup. Do not rerun them for the current repository; in particular, the repository is already initialized and v0.3.0 requires a separate review and release decision.

```bash
python -m pytest tests
git init
git add .
git commit -m "Prepare v0.1.0 GitHub release"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
git tag v0.1.0
git push origin v0.1.0
gh release create v0.1.0 <mp4-file> --title "v0.1.0 - Local Media Automation for Feishu/Lark" --notes-file RELEASE.md
```
