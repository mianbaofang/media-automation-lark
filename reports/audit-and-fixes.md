# 审核与修复记录（evidence）

> 本文件按 yao-meta-skill 规范，把"审核发现 + 修复记录"作为 evidence 沉淀在 `reports/`。

## 2026-07-06 全量审核与修复

审核维度：代码逻辑、健壮性、风控、数据一致性、功能完整性、跨平台、配置、文档一致性、可观测性、测试。

### 已修复

| 编号 | 严重度 | 项 | 处理 |
|------|--------|------|------|
| P0 | 崩溃 | collector `--no-archive`+通知时 `feishu` 未定义 NameError | `feishu` 定义提到归档分支外，mock 验证通过 |
| P1 | 风控 | SSRF 未防（可抓 169.254.169.254/localhost/file://） | `common.is_safe_url` 接入 HttpFetch/material fetch_article/collector RSS |
| P1 | 数据 | 归档无去重，重跑重复写入飞书 | `output/seen.jsonl` 幂等：collector/content-archiver/material/data-collector 写前按 key 去重 |
| P2 | 功能 | 场景 B 只读文件不抓平台 | 新增 `platforms_fetcher.py`（bilibili 公开接口适配器）+ `data-collector --fetch` |
| P2 | UX | env-check 成功消息误导 | 结论按场景分级；加 `validate_config` 告警 |
| P2 | 健壮 | 无 config 校验 | `common.validate_config` |
| P2 | 健壮 | 401/403 时 polish 批量退避耗时 | `llm_chat` 鉴权失败不重试立即降级 |
| P2 | 测试 | 无自动化测试 | `tests/test_core.py`（pytest，覆盖 is_safe_url/validate_config/dedup/polish 降级/anysearch 解析/分类/指标计算） |
| P2 | 跨平台 | cron 仅 Linux | `assets/cron-examples/windows-task-scheduler.md` |
| P3 | 一致 | `table_id`/`archive_table_id` 双键 | 统一 `archive_table_id`，`content-archiver` 兼容旧 `table_id` |
| P3 | 可观测 | collector stdout 混用 | 进度走 stderr，末尾输出结构化 JSON 到 stdout |
| P3 | 文档 | "写表即更新看板"误导 | 改为"写飞书表+本地 HTML 看板；飞书侧需自建仪表盘才自动刷新" |
| P3 | 文档 | llm-prompt-templates 未提 renhua | 加"输出去 AI 味"节指向 renhua-style.md |
| P3 | 文档 | SKILL/openai.yaml 过时 | SKILL"三个脚本"→"各场景脚本"；openai.yaml 补 D/renhua |
| P3 | 代码 | search_backends 死变量 `BS` | 删除 |

### yao 规范化

- 新增 `agents/interface.yaml`（与 SKILL.md 对齐）。
- SKILL.md 加「边界与排除」小节（输入/输出边界、幂等、不包含、降级）。
- evidence 沉淀到 `reports/`（本文件）。
- 分层遵循：guidance→references/，logic→scripts/，evidence→reports/。

### 残留 / 已知限制

- `bilibili` 公开接口可能受站点反爬（wbi/cookie）影响，失败时降级为提示用 `--source` 喂入。
- 微博/抖音等需审核/企业资质的平台未实现自动抓取，留 `--source` 文件入口。
- renhua 对域名 URL 不做 DNS 解析（不防 DNS rebinding），个人用途可接受。
