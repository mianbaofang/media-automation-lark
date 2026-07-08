---
name: media-automation-lark
description: 自媒体自动化工作流（飞书 CLI 版）。当用户要搭建自媒体自动化系统、把内容/RSS/API 数据归档到飞书多维表格、做多平台数据自动可视化看板、或用 AI 管理文章/图片/PDF 素材并归档到飞书云文档时使用。还支持按用户需求自动调用任意搜索后端（anysearch/autocli/tavily/agent-reach/multi-search-engine）从全网采集文章，存成带分类的 Markdown 并归档飞书。核心能力：RSS/API 内容抓取、联网搜索采集、LLM 结构化提取、lark-cli 飞书集成（多维表格/云文档/机器人推送）、数据可视化、图片与 PDF 智能分析。触发词包括"自媒体自动化""内容归档到飞书""数据自动可视化""素材智能管理""自动采集文章""搜索后存成 Markdown""用 lark-cli""@larksuite/cli"。涉及 lark-cli 配置、飞书 API 调用、平台数据抓取、搜索后端集成或 LLM Prompt 优化时，必须优先读取 references/ 中的文档。
---

# 自媒体自动化工作流（飞书 CLI 版）

通过飞书 CLI（`lark-cli`）把自媒体内容的抓取、结构化、归档、可视化与素材管理串成可定时运行的自动化流水线。所有飞书写操作都经由 `lark-cli` 子进程完成，密钥只走环境变量或 `@env:` 占位符，绝不硬编码。

**搜索后端可插拔**：采集能力不依赖某一个搜索引擎。运行时自动检测 `anysearch` / `autocli` / `tavily` / `agent-reach` / `multi-search-engine` 哪些已安装可用；缺失的后端跳过，没有就降级到 RSS，绝不让流程崩溃。详见 `references/search-backends.md`。

**对外文字统一过 renhua（人话）去 AI 味**：本 skill 产出的所有中文文字——摘要、标题、索引、归档正文摘要，以及本助手关于交付物的回复——都先经 `renhua` 提示词润色再输出，去掉 AI 腔、保留事实与作者判断。`renhua` 是提示词型技能（非 CLI），安装时由 `--auto-install` 从 GitHub 拉取；规则运行时从已安装的 `renhua/SKILL.md` 读取（单一事实源），无 LLM key 时自动跳过润色、不阻断流程。详见 `references/renhua-style.md`。

## 前置依赖

- Node 包（全局）：`@larksuite/cli` → `npm install -g @larksuite/cli` 然后 `npx skills add larksuite/cli -y -g`，重启 AI 工具。
- Python 包：`requests`、`feedparser`、`beautifulsoup4`、`pandas`、`openpyxl`、`python-docx`、`PyPDF2`、`markitdown`（场景 C 文件入库用，装 `markitdown[all]` 以支持 docx/pptx/xlsx/epub 等）。
- 飞书：创建多维表格拿到 `app_token` 与 `table_id`；`lark-cli config init` + `lark-cli auth login --recommend`。
- 各平台 API Key 通过环境变量注入（如 `LARK_LLM_API_KEY`、`WEIBO_API_KEY`）。
- **搜索后端（可选，按需）**：采集场景 D 需要。零配置可用 `anysearch`（免 key）；其它可选 `tavily`（需 key）、`autocli`（需 Chrome 登录态）、`agent-reach`、`multi-search-engine`。**初次安装时从 GitHub 拉取缺失后端**，见步骤 1。

## 开源用户上手（首次使用）

本 skill 面向开源，所有外部依赖都可自动检测、提示缺失并按需安装：

1. **放入 skills 目录**：把本 skill 文件夹放到 `~/.workbuddy/skills/media-automation-lark`（WorkBuddy 自动发现）。
2. **检测环境与缺失依赖**：
   ```bash
   python3 scripts/env-check.py
   ```
   会列出 Python/Node/lark-cli、各搜索后端、renhua 的状态，并汇总「缺失的外部 skill」。
3. **安装缺失依赖**（二选一）：
   - 逐项确认（人工推荐）：
     ```bash
     python3 scripts/install_backends.py --interactive
     ```
     缺哪个问哪个，回车默认装、`n` 跳过。
   - 一次性全装（CI/已知情）：
     ```bash
     python3 scripts/install_backends.py --all
     ```
   - 在 WorkBuddy 对话里，也可直接让我检测后帮你装——我会先列出缺失项，你同意后再装。
4. **配置**：复制 `config.json.example` 为 `config.json`，填飞书 `app_token`/`table_id`/`chat_id`，密钥保持 `@env:`。
5. **新手面板**：当用户说“不会用”“打开面板”“开始配置”“先检查环境”时，Agent 必须直接调用 `scripts/panel-agent.py start --open`，再把返回的 URL 给用户；不要要求用户复制命令。
6. **本地预览验证**：各场景脚本加 `--dry-run`，先确认本地产物再写入飞书。

## Agent 面板入口

普通用户不应被要求手动输入启动命令。遇到首次使用、用户反馈不会用、需要 GUI、需要检查环境或配置飞书时，先由 Agent 调用 `scripts/panel-agent.py start --open`。该启动器会返回 JSON，包含 `ok`、`status`、`url`、`pid` 和 `log`；启动成功后把 `url` 返回用户，启动失败时读取 `log` 并继续排查。

面板默认只做本地预览。六个入口必须用普通用户能理解的任务语言呈现：检查环境、先体验一次完整流程、直接整理网页或文件、按选题采集公开内容、归档 RSS 订阅、生成看板并准备定时任务。只有用户在面板中勾选“写入飞书”时，才允许调用飞书写入能力。

### 外部 skill 依赖表

| 名称 | 用途 | 是否必需 | 来源 / 安装 |
|------|------|----------|-------------|
| anysearch | 搜索+抓取（免 key） | 场景 D 推荐 | github.com/anysearch-ai/anysearch-skill |
| tavily | 搜索+抓取（需 key） | 可选 | cli.tavily.com/install.sh；skill: github.com/tavily-ai/skills |
| autocli | 抓取登录态页面 | 可选 | github.com/nashsu/AutoCLI/releases；skill: github.com/nashsu/AutoCLI-skill |
| agent-reach | 多平台搜索（交互） | 可选 | github.com/Panniantong/Agent-Reach |
| multi-search-engine | 17 引擎搜索（交互） | 可选 | WorkBuddy 技能市场 |
| renhua | 去 AI 味润色 | 推荐 | github.com/Pluviobyte/rnskill |
| lark-cli | 飞书写入 | 场景 A/B/C 必需 | npm i -g @larksuite/cli |
| markitdown | 文件转 Markdown（pip 包，**非 GitHub skill**） | 场景 C 文件入库可选 | `pip install 'markitdown[all]'`；由 `env-check --auto-install` 或 `install_backends.py` 自动装 |

> 安装细节见 `references/search-backends.md` 与 `references/renhua-style.md`；地址以各项目官方为准。缺失时脚本不会崩溃，只降级或提示。markitdown 是 pip 包不是 skill，单独走 pip 安装（见上表），不进 GitHub 克隆流程。

## 标准操作流程

### 步骤 1 · 环境检测与初始化

1. 运行 `scripts/env-check.py --auto-install`：自动检测并安装缺失依赖，**同时从 GitHub 拉取缺失的搜索后端与 `renhua` 润色技能**（已装的跳过），生成 `config.json.example` 模板。
2. 复制 `config.json.example` 为 `config.json`，填写 `app_token` / `table_id` / `chat_id` 等；密钥段保持 `"@env:VAR_NAME"` 形式。
3. 配置飞书 CLI 授权：读取 `references/lark-cli-setup.md` 后执行 `lark-cli config init` 与 `lark-cli auth login --recommend`。
4. （可选）单独安装/查看搜索后端：`python3 scripts/install_backends.py --all`；查看哪些可用：`python3 scripts/search_backends.py`。

### 步骤 2 · 选择工作流场景

| 场景 | 脚本 | 做什么 |
|------|------|--------|
| **A 内容自动存档** | `scripts/content-archiver.py` | RSS/API 抓取 → LLM 结构化提取 → 写入飞书多维表格 |
| **B 数据搜集+可视化** | `scripts/data-collector.py` | 多平台指标抓取/导入 → 计算互动率等指标 → 写飞书并生成 HTML 看板 |
| **C 多模态素材管理** | `scripts/material-manager.py` | 文章链接/图片/PDF/本地文件(docx/pptx/xlsx/epub/html/音频) → markitdown 转 Markdown → AI 分析 → 归档飞书云文档 + 素材表 |
| **D 智能搜索采集→分类 Markdown** | `scripts/collector.py` | 按选题清单调用可用搜索后端 → 可限定公开来源范围 → 按爆款线索/相关度/分类/作者排序 → 抓正文 → 按分类存 Markdown → 可选归档飞书 |
| **新手控制面板** | `scripts/panel-agent.py` → `scripts/gui-panel.py` | Agent 打开浏览器面板；面板内运行环境检查、安全样例体验、网页/文件整理、RSS、选题采集、看板和定时准备，默认不写飞书 |

各场景脚本共用 `scripts/common.py`（配置、密钥、LLM、lark-cli 封装、HTTP 重试、renhua 润色）。所有脚本均支持 `--dry-run`（不写飞书，仅生成本地备份/预览）与 `--yes`（跳过高风险确认），首次运行务必先本地预览验证。

- 新手面板：Agent 调用 `scripts/panel-agent.py start --open` → 返回 `http://127.0.0.1:8787`
- 场景 A：`python3 scripts/content-archiver.py --rss-url "<url>" --dry-run`
- 场景 B：`python3 scripts/data-collector.py --fetch --push`（自动抓 `platforms`；或 `--source metrics.json` 喂入文件）→ 写飞书多维表格并生成本地 HTML 看板（飞书侧需自建仪表盘才自动刷新）
- 场景 C：`python3 scripts/material-manager.py --url "<article>" --dry-run`
- 场景 D：`python3 scripts/collector.py --query "LLM 应用落地" --source-scope bilibili --rank-by hotness --category-map "AI:大模型,LLM,Agent" --dry-run`
  - 先用 `--offline-demo` 跑通安全样例（不联网、不写飞书）；用 `--source-scope` 选择公开来源范围；用 `--rank-by` 选择爆款线索、相关度、分类或作者优先；用 `--no-fetch` 只列 URL 不抓正文；用 `--backends anysearch` 限定后端。

### 场景 D 详解（自动搜索 + 分类 Markdown）

流程：用户给出选题清单（CLI `--query` 可重复，或 `config.json` 的 `search.queries`）
→ `collector.py` 根据 `--source-scope` / `--source-filter` 限定公开来源范围
→ 运行时检测可用搜索后端，跨后端收集候选 URL（去重）
→ 根据 `--rank-by` 对候选结果排序（爆款线索只使用搜索结果文本中公开可见的阅读、播放、点赞、收藏、评论、分享等线索；没有线索时退回相关度）
→ 用可用抓取后端取每篇正文（autocli `read` / anysearch `extract` / tavily `extract` / http 兜底）
→ 按 `category_map` 关键词匹配归类（命中则入对应目录，否则入 `default_category`）
→ 写入 `<output_dir>/<分类>/<日期>-<标题>.md`（带 frontmatter：标题/来源/日期/分类/标签/后端），并生成 `index.md`
→ 若配置了飞书 `archive_table_id`，批量写入多维表格；可选机器人推送。

**关键集成点（务必读 `references/search-backends.md`）**：
- 搜索后端在 `scripts/search_backends.py` 注册，含运行时检测与 GitHub 安装信息。
- 安装时由 `scripts/install_backends.py` 从 GitHub 拉取缺失后端；已装的自动跳过。
- `agent-reach` / `multi-search-engine` 仅在**交互模式**由我（agent）编排，不进无头脚本（前者依赖 mcporter/登录态，后者依赖 WebFetch 工具）。
- 没有任何可用搜索后端且没给 RSS 时，`collector.py` 给出安装命令并以退出码 2 结束——不静默失败。

### 文本润色（renhua / 人话）

所有对外中文文字都经 `renhua` 改写后再输出，落实"所有文字修饰整理好再输出"。机制：

- **安装**：`--auto-install` 或 `install_backends.py --all` 从 `https://github.com/Pluviobyte/rnskill` 拉取 `skills/renhua` 到用户 skills 目录。
- **规则来源**：运行时 `common.find_renhua_skill()` 读取已安装的 `renhua/SKILL.md` 作改写规则（单一事实源）；未安装则用 `common._RENHUA_FALLBACK` 内置精简规则。
- **调用点**：`common.polish_text(text, config)` 调 LLM 套用规则。已接入——场景 A 的摘要/核心观点、场景 C 的摘要/要点/行动项、场景 D 的索引简介（及 `--polish-body` 时的正文）。
- **开关**：`config.json` 的 `text.polish`（默认 true）总开关；场景 D 另有 `--no-polish` 与 `--polish-body`。`text.polish_body` 默认 false——正文默认保留抓取原文（归档真实性），仅润色本 skill 生成的文字。
- **降级**：未配 LLM key 或调用失败，`polish_text` 原样返回，不阻断。

### 步骤 3 · 配置定时任务

直接复用 `assets/cron-examples/crontab.txt`（crontab 行）或 `assets/cron-examples/systemd-timer.md`（systemd service+timer）。**不要**手写新的重试/调度逻辑，模板已覆盖常见场景。示例：

```cron
0 23 * * * /usr/bin/python3 /path/to/scripts/content-archiver.py --rss-url "<url>" >> /var/log/media/archiver.log 2>&1
```

测试运行：`python3 scripts/content-archiver.py --rss-url "<url>"` 后到飞书多维表格确认记录已写入、字段完整。

### 步骤 4 · 验证与优化

- 检查飞书多维表格记录与字段完整性；用 `--dry-run` 比对本地 `output/*_backup.json`。
- 提取/分析不准时，调 `references/llm-prompt-templates.md` 中的 Prompt（加 few-shot、收紧枚举、明确 `null` 规则）。
- 配置飞书机器人推送：在 `config.json` 填 `feishu.chat_id`，脚本完成时会用 `lark-cli im +messages-send --as bot` 推送汇总。

## 注意事项（强制）

- **法律合规与免责声明**：使用前必须阅读仓库根目录 `DISCLAIMER.md`。所有网页获取、搜索采集、RSS/API 抓取和浏览器自动化都仅限学习研究，必须遵守法律、平台 ToS、robots.txt 与接口限制；禁止高频大规模抓取、采集个人隐私、绕过风控或对外提供未经授权的数据采集服务。
- **脆弱操作必须调用脚本**：API 鉴权、数据格式转换、指标计算、重试、搜索后端调用——均在 `scripts/` 内实现，不要在对话里手写等效逻辑。搜索后端集成细节见 `references/search-backends.md`。
- **搜索后端可插拔**：运行时自动检测，缺失则跳过或降级到 RSS；不要因为某个后端没装就判定 skill 不可用。新的搜索工具接入只在 `scripts/search_backends.py` 的 `REGISTRY` 加一项。
- **lark-cli / 飞书 / 平台 / Prompt 相关**：优先读 `references/lark-cli-setup.md`、`references/api-integration.md`、`references/llm-prompt-templates.md`。
- **密钥安全**：只走环境变量或 `@env:` 占位符，禁止硬编码；`.env` 权限设 `600` 且不提交。`tavily`/`anysearch` 等后端的 key 同样走环境变量。
- **重试间隔**：脚本内置指数退避，集中在 `common.py`，不要手动修改重试次数/间隔。
- **中文环境**：输出与飞书字段用中文；终端设置 `PYTHONIOENCODING=utf-8` 防乱码。
- **对外文字去 AI 味（renhua）**：本 skill 产出的中文文字必须过 `renhua` 润色后再输出（见上节）。不要为了"通顺"手动给 LLM 摘要套 AI 腔模板。润色规则以已安装的 `renhua/SKILL.md` 为准，不要另写一套风格规则。

## 边界与排除

- **输入边界**：抓取/采集的 URL 经 `common.is_safe_url` 做 SSRF 过滤（拦截 `file://`、loopback、link-local、cloud metadata、私网，除非显式允许）。正文为抓取原文，保留真实性，默认不经 renhua 改写。
- **输出边界**：本 skill 产出的中文文字（摘要/标题/索引/通知）默认经 renhua 去 AI 味；抓取原文不改写。
- **幂等**：写飞书前按 URL /（日期+平台）/ 素材哈希去重（`output/seen.jsonl`），重跑不重复写入。
- **不包含**：不实现需审核/企业资质的平台私有 API（微博/抖音等），此类用 `--source` 文件喂入；已实现 bilibili 公开接口自动抓取。
- **降级**：缺搜索后端→RSS 或退出码 2；缺 LLM key→提取/润色原样返回；缺 lark-cli→写飞书不可用，仅生成本地产物。

## 资源索引

- `scripts/env-check.py` — 环境检测与依赖安装，生成 config 模板（含搜索后端）
- `scripts/collector.py` — 场景 D：搜索采集 → 分类 Markdown（含后端检测/降级）
- `scripts/search_backends.py` — 搜索后端注册表：运行时检测 + 调用适配器
- `scripts/install_backends.py` — 安装时从 GitHub 拉取缺失的搜索后端
- `scripts/content-archiver.py` — 场景 A：RSS/API 抓取与归档
- `scripts/data-collector.py` — 场景 B：多平台数据抓取与可视化
- `scripts/material-manager.py` — 场景 C：多模态素材分析与归档
- `scripts/common.py` — 共享模块（配置/密钥/LLM/lark-cli/HTTP）
- `scripts/file2md.py` — 文件转 Markdown 薄封装（基于 microsoft/markitdown，缺失优雅降级）
- `references/lark-cli-setup.md` — 飞书 CLI 配置参考
- `references/api-integration.md` — 各平台 API 接入指南
- `references/llm-prompt-templates.md` — LLM Prompt 模板
- `references/search-backends.md` — 搜索后端接入指南（检测/安装/降级）
- `references/renhua-style.md` — 文本润色（renhua / 人话）接入指南
- `assets/cron-examples/` — 定时任务配置示例（crontab / systemd）
