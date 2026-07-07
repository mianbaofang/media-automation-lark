# Media Automation Lark / 自媒体自动化工作流（飞书 CLI 版）

![workflow](assets/media-automation-lark-flow.svg)

把内容抓取、搜索采集、素材分析、数据看板和飞书归档串成一套可定时运行的本地自动化工作流。项目使用 Python 脚本编排 RSS/API、搜索后端、文件转 Markdown、LLM 结构化提取和 `lark-cli` 写入飞书多维表格、云文档与机器人通知。

> 使用前请先阅读 [免责声明 / Disclaimer](DISCLAIMER.md)。本项目仅供学习和研究，任何网页获取、搜索采集或平台数据抓取都必须遵守法律、平台 ToS 和 robots.txt。

## 产品预览

![Media Automation Lark demo](assets/media-automation-lark-demo.gif)

这条链路面向内容团队的日常成本：把搜索、抓取、素材入库、数据复盘和飞书同步收进一个可预览、可空跑、可定时的流程里。人只处理判断和取舍，重复搬运交给脚本。

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

## 先跑一个离线演示

不联网、不写飞书，只验证分类和 Markdown 生成：

```bash
python scripts/collector.py --offline-demo --category-map "AI:大模型,LLM,Agent;产品:增长" --output-dir output_demo --no-archive --no-notify --no-polish
```

生成后查看 `output_demo/index.md`。确认没问题再改用真实搜索、RSS 或 API。

## 常用命令

```bash
# 环境检查
python scripts/env-check.py

# 安装可选搜索/转换后端
python scripts/install_backends.py --interactive

# RSS 内容归档，先 dry-run
python scripts/content-archiver.py --rss-url "https://example.com/feed.xml" --dry-run

# 搜索采集并分类保存 Markdown
python scripts/collector.py --query "LLM 应用落地" --category-map "AI:大模型,LLM,Agent" --dry-run

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

## 安全和合规设计

- URL 入口使用 `common.is_safe_url` 拦截 `file://`、localhost、link-local、云元数据地址和私网地址。
- 密钥只走环境变量或 `@env:` 占位符；`config.json`、`.env` 已加入 `.gitignore`。
- 所有写飞书动作都支持 `--dry-run`，首次运行建议先空跑。
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
scripts/                 核心脚本
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
- 开源协议：`LICENSE`
- Issue / PR 模板：`.github/`
- 发布检查清单：`reports/github-launch-checklist.md`
- 致谢清单：见 README「致谢」
- HyperFrames 时间流短片源码：`hyperframes/media-automation-lark-timeline/`
- MiniMax CLI 配乐：`hyperframes/media-automation-lark-timeline/assets/audio/minimax-bgm.mp3`
- README 动图预览：`assets/media-automation-lark-demo.gif`
- 轻量工作流动画：`assets/media-automation-lark-flow.svg`
- 静态流程图：`media-automation-skill-workflow.png`

## 状态

当前版本按 `v0.1.0` 准备公开发布。测试命令：`python -m pytest tests`。

配乐版 HyperFrames MP4 已导出到桌面：`media-automation-lark-timeline-music.mp4`。

开源协议：MIT，详见 [LICENSE](LICENSE)。
