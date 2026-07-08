# Media Automation Lark / 自媒体自动化工作流（飞书 CLI 版）

<p align="center">
  <a href="https://github.com/mianbaofang/media-automation-lark/releases/tag/v0.1.0">
    <img src="assets/media-automation-lark-demo.gif" alt="Media Automation Lark 产品预览动画" width="100%">
  </a>
</p>

<p align="center">
  <a href="README.en.md">English</a>
  ·
  <a href="SKILL.md">Skill</a>
  ·
  <a href="DISCLAIMER.md">免责声明</a>
  ·
  <a href="ACKNOWLEDGEMENTS.md">致谢</a>
  ·
  <a href="RELEASE.md">发布说明</a>
  ·
  <a href="CHANGELOG.md">更新日志</a>
  ·
  <a href="SECURITY.md">安全说明</a>
  ·
  <a href="reports/project-audit.md">审查报告</a>
</p>

## 为什么做这个项目

做内容账号时，真正消耗人的往往不是某一次创作，而是每天重复的小搬运：打开不同平台找选题，把网页、RSS、PDF、图片和表格拆开保存，再把数据看板、素材记录和待办同步到飞书。

这些动作单独看都不复杂，但一天下来会把判断力切碎。素材可能散在下载目录、聊天记录和浏览器收藏里；数据复盘要来回复制；一个选题从搜索、抓取、整理到归档，常常还没开始判断价值，就已经花掉很多耐心。

我做这个项目，是想把这些重复转移收进一个本地可控的流程：先在本地预览，再决定是否抓取、转换、分析和写入飞书。人保留判断、取舍和创意，脚本负责那些每天都要重复、但不该占用注意力的部分。

把内容抓取、搜索采集、素材分析、数据看板和飞书归档串成一套可定时运行的本地自动化工作流。项目使用 Python 脚本编排 RSS/API、搜索后端、文件转 Markdown、LLM 结构化提取和 `lark-cli` 写入飞书多维表格、云文档与机器人通知。

> 使用前请先阅读 [免责声明 / Disclaimer](DISCLAIMER.md)。本项目仅供学习和研究，任何网页获取、搜索采集或平台数据抓取都必须遵守法律、平台 ToS 和 robots.txt。

## 工作流概览

<p align="center">
  <img src="assets/media-automation-lark-flow.svg" alt="Media Automation Lark workflow" width="100%">
</p>

这条链路面向内容团队的日常成本：把搜索、抓取、素材入库、数据复盘和飞书同步收进一个可预览、可定时的流程里。人只处理判断和取舍，重复搬运交给脚本。

## 能做什么

| 场景 | 脚本 | 输出 |
|---|---|---|
| 内容自动存档 | `scripts/content-archiver.py` | RSS/API 内容结构化后写入飞书多维表格 |
| 数据搜集与看板 | `scripts/data-collector.py` | 平台指标汇总、`dashboard.html`、`metrics.xlsx`、可选写飞书 |
| 多模态素材管理 | `scripts/material-manager.py` | 文章、图片、PDF、Office 文件转 Markdown 并归档飞书云文档 |
| 搜索采集分类 | `scripts/collector.py` | 按关键词搜索网页，抓正文，分类写入 Markdown，可选归档飞书 |

## 快速开始

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/env-check.py --gen-config
copy config.json.example config.json
```

然后编辑 `config.json`：

- 飞书：填 `feishu.app_token`、`archive_table_id`、`metrics_table_id`、`materials_table_id`、`chat_id`。
- LLM：默认从 `LARK_LLM_API_KEY` 读取密钥，配置里保持 `@env:LARK_LLM_API_KEY`。
- 平台：B 站自动抓取需填 `platforms.bilibili.mid`；受限平台建议用 `--source` 导入 JSON/CSV。

首次连接飞书前，还需要安装并登录 `lark-cli`：

```bash
npm install -g @larksuite/cli
lark-cli config init
lark-cli auth login --recommend
```

## 新手入口：让 Agent 打开面板

普通用户不用记脚本参数。对支持本 Skill 的 Agent 说“打开 Media Automation Lark 面板”或“先帮我检查环境”，Agent 会直接启动本地控制台并返回访问地址。

面板地址默认为 <http://127.0.0.1:8787>。面板默认只做本地预览，可完成六类任务：检查环境、先体验一次完整流程、直接整理网页或文件、按选题采集公开内容、归档 RSS 订阅、生成看板并准备定时任务；只有勾选“写入飞书”时才会调用飞书写入。

## 先体验一次完整流程

如果第一次不知道这个项目会产出什么，可以先跑内置样例。不联网、不写飞书，只验证分类和 Markdown 生成：

```bash
python scripts/collector.py --offline-demo --category-map "AI:大模型,LLM,Agent;产品:增长" --output-dir output_demo --no-archive --no-notify --no-polish
```

生成后查看 `output_demo/index.md`。确认结果样式没问题，再改用真实网页、文件、RSS 或搜索选题。

## 常用命令

```bash
# 环境检查
python scripts/env-check.py

# 安装可选搜索/转换后端
python scripts/install_backends.py --interactive

# RSS 内容归档，先 dry-run
python scripts/content-archiver.py --rss-url "https://example.com/feed.xml" --dry-run

# 搜索采集并分类保存 Markdown；可指定公开来源范围和排序目标
python scripts/collector.py --query "LLM 应用落地" --source-scope bilibili --rank-by hotness --category-map "AI:大模型,LLM,Agent" --dry-run

# 平台指标抓取，只抓 B 站
python scripts/data-collector.py --fetch --platform bilibili --dry-run

# 文件素材入库
python scripts/material-manager.py --file "./report.pdf" --dry-run

# 自动化测试
python -m pytest tests
```

## 搜索和抓取后端

项目会在运行时检测后端，装了就用，没装就跳过：

- `anysearch`：搜索 + 抓取，免 key，推荐。
- `tavily`：搜索 + 抓取，需 `TAVILY_API_KEY` 或 `tvly login`。
- `autocli`：读取登录态网页并转 Markdown。
- `agent-reach` / `multi-search-engine`：仅适合交互模式，不进无头定时脚本。
- `http`：内置 HTTP + BeautifulSoup 兜底抓取。

细节见 [references/search-backends.md](references/search-backends.md)。

面板里的“按选题去采集”会让用户先选来源范围、采集清单和排序目标。爆款排序只使用公开搜索结果里可见的阅读、播放、点赞、收藏、评论等文本线索；如果结果里没有这些线索，会自动退回相关度排序。

## 安全和合规设计

- URL 入口使用 `common.is_safe_url` 拦截 `file://`、localhost、link-local、云元数据地址和私网地址。
- 密钥只走环境变量或 `@env:` 占位符；`config.json`、`.env` 已加入 `.gitignore`。
- 所有写飞书动作都支持 `--dry-run`，首次运行建议先本地预览。
- 抓取正文默认保留原文，不做自动改写；项目只润色自己生成的摘要、通知和索引文字。
- 本项目不绕过验证码、登录限制、付费墙、加密或平台风控。

## 致谢

本项目的文件处理、网页解析、数据表格和可选搜索能力，建立在这些开源项目与工具生态之上：

- Python 基础库生态：`requests`、`feedparser`、`beautifulsoup4`、`pandas`、`openpyxl`、`python-docx`、`PyPDF2`。
- 文件转 Markdown：Microsoft [`markitdown`](https://github.com/microsoft/markitdown)。
- 可选搜索 / 抓取后端：[`anysearch-skill`](https://github.com/anysearch-ai/anysearch-skill)、[`AutoCLI`](https://github.com/nashsu/AutoCLI)、[`Agent-Reach`](https://github.com/Panniantong/Agent-Reach)。
- 可选检索服务与工具链：Tavily CLI / API、飞书开放平台与 `@larksuite/cli`。
- 演示视频制作链路：HyperFrames 时间流动画与 MiniMax CLI 配乐生成。

## 项目结构

```text
scripts/                 核心脚本（含 Agent 面板入口 panel-agent.py）
references/              飞书、API、搜索后端、Prompt 参考
assets/cron-examples/    crontab、systemd、Windows 任务计划示例
agents/                  Agent/技能接口描述
tests/                   pytest 单测
reports/                 审查记录和发布前检查
```

## 发布资料

- 中文说明：`README.md`
- English README：`README.en.md`
- 免责声明：`DISCLAIMER.md`
- 发布说明：`RELEASE.md`
- 变更日志：`CHANGELOG.md`
- 贡献指南：`CONTRIBUTING.md`
- 安全说明：`SECURITY.md`
- 致谢：`ACKNOWLEDGEMENTS.md`
- 开源协议：`LICENSE`
- Issue / PR 模板：`.github/`
- 发布检查清单：`reports/github-launch-checklist.md`
- 致谢清单：`ACKNOWLEDGEMENTS.md`
- HyperFrames 时间流短片源码：`hyperframes/media-automation-lark-timeline/`
- MiniMax CLI 配乐：`hyperframes/media-automation-lark-timeline/assets/audio/minimax-bgm.mp3`
- README 动图预览：`assets/media-automation-lark-demo.gif`
- 轻量工作流动画：`assets/media-automation-lark-flow.svg`
- 静态流程图：`media-automation-skill-workflow.png`
- Agent 面板入口：`scripts/panel-agent.py`

## 状态

当前公开版本：[`v0.1.0`](https://github.com/mianbaofang/media-automation-lark/releases/tag/v0.1.0)。

- 验证：`python -m pytest tests`。
- 动画：README 使用轻量 GIF 预览；配乐版 MP4 已作为 `v0.1.0` Release 附件发布。
- 源码：HyperFrames 时间流短片保留在 `hyperframes/media-automation-lark-timeline/`。

开源协议：MIT，详见 [LICENSE](LICENSE)。
