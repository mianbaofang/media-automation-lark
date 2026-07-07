# GitHub Launch Checklist

## Ready

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
- Music-backed MP4 export: `C:\Users\Ethan\Desktop\media-automation-lark-timeline-music.mp4`
- Tests: `python -m pytest tests`

## Recommended GitHub Repository Settings

- Description: `Local media automation toolkit for Feishu/Lark: content archiving, search collection, material management, and analytics dashboards.`
- Topics: `python`, `feishu`, `lark`, `bitable`, `content-automation`, `media-workflow`, `rss`, `markdown`, `automation`, `dashboard`
- First release title: `v0.1.0 - Local Media Automation for Feishu/Lark`
- Website/social preview: use `assets/media-automation-lark-demo.gif` or `media-automation-skill-workflow.png`

## Needs Your Decision

- Decide whether to publish the desktop MP4 as a GitHub release asset. The README uses the lighter GIF preview.
- Initialize Git and connect the remote when you are ready to publish.

## Final Local Commands

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
```
