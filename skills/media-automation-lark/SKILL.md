---
name: media-automation-lark
description: Feishu content automation and Lark content workflows for creators and small teams. Use it for a Lark content workflow or RSS to Feishu archiving when users want to collect RSS/API feeds and public webpages, organize articles and files, build metrics dashboards, preview locally, or optionally write reviewed results to Feishu/Lark Bitable or Docs. 适用于将 RSS/API、公开网页、文章、图片、PDF、Office 文件或平台指标整理成 Markdown、数据看板或飞书多维表格/云文档，也用于按选题采集公开内容、启动本地控制面板、配置 lark-cli 或给生成文字做 renhua 去 AI 味润色。触发词包括“自媒体自动化”“内容归档到飞书”“搜索采集”“素材管理”“数据看板”“打开面板”“用 lark-cli”。
license: MIT
---

# 自媒体自动化工作流（飞书 CLI 版）

仓库级 `reports/` 只保存审计与信任证据，不属于运行时输入，也不随安装包发布；`evals/` 保存可重复运行的触发边界样例，`evals/output/` 另外保存输出契约评测的固定案例与输入 fixture。输出评测用于验证索引、看板、本地预览和安全边界等最终产物，不是运行时输入，也不随安装包发布。

## 执行骨架

1. 先读 `DISCLAIMER.md` 和 `references/workflow.md`；涉及飞书、搜索后端、API 或 Prompt 时再读对应参考文档。
2. 运行 `python scripts/env-check.py` 检查依赖。用户说“不会用”“打开面板”或“先检查环境”时，直接调用 `python scripts/panel-agent.py start --open` 并返回 URL。
3. 根据任务选择 `content-archiver.py`、`data-collector.py`、`material-manager.py` 或 `collector.py`；首次真实运行使用 `--dry-run`，搜索先用 `--offline-demo`（仅内置样例，不联网）。
4. 检查本地产物、分类、去重和摘要后，只有用户明确要求时才写入飞书；缺依赖、缺 key 或后端不可用时给出可执行降级提示。

`--offline-demo` 只检查搜索分类和 Markdown 写盘；`--dry-run` 仍可能读取真实输入或公开接口，但跳过飞书写入与机器人通知。B 站指标运行前先复制 `config.json.example` 为 `config.json`，把 `platforms.bilibili.mid` 填成数字 UID，再显式传入 `--config config.json`。本 Skill 不启动常驻调度器，定时任务由用户配置的 cron、systemd timer 或 Windows Task Scheduler 负责。

## 输出与安全边界

- 输出是本地 Markdown、JSON 备份、HTML 看板，或用户明确授权的飞书记录；源文件默认只读。
- URL 入口必须经过轻量的 `common.is_safe_url` 输入检查，拒绝非 HTTP(S)、localhost、云元数据主机以及字面上的 loopback、link-local、私网和保留 IP。普通域名不会做 DNS 解析，因此这不是完整的 SSRF 防护。
- 密钥只走环境变量或 `@env:`；不绕过登录限制、验证码、付费墙、加密或平台风控。
- 生成的中文摘要、标题、索引和通知默认按已安装 `renhua/SKILL.md` 规则润色；抓取正文保留原文，无 LLM key 时原样返回。

## 资源

- `scripts/`：检测、面板、RSS/API、搜索采集、素材管理和飞书调用。
- `references/workflow.md`：完整场景分支、命令、降级和定时任务顺序。
- `references/`：飞书 CLI、API、Prompt、搜索后端和 renhua 规则。
- `assets/cron-examples/`：已审核的 crontab、systemd 和 Windows 任务模板。
