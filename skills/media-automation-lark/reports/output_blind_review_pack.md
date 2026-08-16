# Output Blind A/B Review Pack

This pack hides whether Variant A or Variant B came from the baseline or the Skill output.
Review the visible rubric first; keep the separate answer key closed until decisions are recorded.

- Pairs: `5`
- Seed: `yao-output-eval-blind-v1`
- Answer key separate: `true`

## Case: offline-search-archive

Prompt: 把一组固定的选题搜索样例离线整理成可分类、可回看的 Markdown 索引。

Rubric:
- `search-index` (1.0): 生成可回看的采集索引。
- `search-count` (1.0): 索引记录离线样例条目数。
- `search-category` (1.0): 结果按分类写入 Markdown frontmatter。
- `search-source` (1.0): 文章保留可追溯来源链接。
- `search-offline` (1.0): 运行证据明确来自离线演示。

### Variant A

CASE=offline-search-archive
EXECUTION_MODE=command
PROVIDER_BACKED=false
EXIT_CODE=0
COMMAND=<python> <repo>/skills/media-automation-lark/scripts/collector.py --config <tmp>/search-config.json --offline-demo --no-archive --no-notify
DURATION_MS=<elapsed>
STDOUT:
STDERR:
【后端检测】
  ✓ anysearch    AnySearch（免key也能用）  — 可用
  ✓ tavily       Tavily（需API key）  — 可用
  ✓ autocli      AutoCLI（复用Chrome登录态，read出Markdown）  — 可用
  ✓ agent_reach  Agent Reach（15平台，交互编排）  — 交互模式可用
  ✓ multi_search Multi Search Engine（17引擎，免key，依赖WebFetch）  — 交互模式可用
  ✓ http         HTTP 兜底（requests+BeautifulSoup）  — 可用

[OFFLINE-DEMO] 已写入 2 篇示例到 <tmp>/search-output
  索引: <tmp>/search-output/index.md
ARTIFACT AI/<date>-Agent_在自媒体运营中的用法.md:
---
title: "Agent 在自媒体运营中的用法"
source: "https://example.com/agent-media"
date: <date>
category: "AI"
query: "LLM 应用落地"
backend: "anysearch"
tags: [AI]
---

# Agent 在自媒体运营中的用法

> 来源: [https://example.com/agent-media](https://example.com/agent-media)  ·  检索词: LLM 应用落地  ·  后端: anysearch

# Agent 在自媒体运营中的用法

正文示例：自动采集、分类、定时发布。
ARTIFACT AI/<date>-如何用_LLM_重构客服工作流.md:
---
title: "如何用 LLM 重构客服工作流"
source: "https://example.com/llm-support"
date: <date>
category: "AI"
query: "LLM 应用落地"
backend: "anysearch"
tags: [AI]
---

# 如何用 LLM 重构客服工作流

> 来源: [https://example.com/llm-support](https://example.com/llm-support)  ·  检索词: LLM 应用落地  ·  后端: anysearch

# 如何用 LLM 重构客服工作流

正文示例：通过检索增强降低幻觉……
ARTIFACT index.md:
# 采集索引

生成时间: <fixed>
条目数: 2

本次共采集 2 篇内容，覆盖 1 个分类。

## AI
- [如何用 LLM 重构客服工作流](AI/<date>-如何用_LLM_重构客服工作流.md) — https://example.com/llm-support
- [Agent 在自媒体运营中的用法](AI/<date>-Agent_在自媒体运营中的用法.md) — https://example.com/agent-media


### Variant B

把两条搜索结果列成一个无分类的标题清单，不生成索引，也不保留来源元数据。

## Case: metrics-dashboard

Prompt: 用固定的两天指标数据生成本地运营看板，并在预览模式下不写入飞书。

Rubric:
- `dashboard-file` (1.0): 输出本地 HTML 看板。
- `dashboard-total` (1.0): 看板保留固定输入的总阅读数。
- `dashboard-rate` (1.0): 看板显示互动率。
- `dashboard-chart` (1.0): 看板包含每日趋势图。
- `dashboard-dry-run` (1.0): 预览模式不写入飞书。

### Variant A

把阅读、点赞和评论数字打印出来，不生成 HTML 看板，也不说明互动率或写入状态。

### Variant B

CASE=metrics-dashboard
EXECUTION_MODE=command
PROVIDER_BACKED=false
EXIT_CODE=0
COMMAND=<python> <repo>/skills/media-automation-lark/scripts/data-collector.py --source <repo>/skills/media-automation-lark/evals/output/fixtures/metrics.json --config <tmp>/dashboard-config.json --dry-run --no-notify
DURATION_MS=<elapsed>
STDOUT:
{"ok": true, "summary": {"total_reads": 1500, "total_likes": 150, "total_comments": 75, "total_shares": 75, "engagement_rate": 0.2, "days": 2, "platforms": ["bilibili"]}, "written": 0, "dashboard": "<path>", "insight": {}}
STDERR:
<timestamp> INFO 汇总: {'total_reads': 1500, 'total_likes': 150, 'total_comments': 75, 'total_shares': 75, 'engagement_rate': 0.2, 'days': 2, 'platforms': ['bilibili']}
<timestamp> INFO 看板已生成: <tmp>/dashboard-output/dashboard.html
<timestamp> INFO 指标表已导出: <tmp>/dashboard-output/metrics.xlsx
<timestamp> INFO 未写入飞书（需 --push 且配置 metrics_table_id，或 --report-yesterday）。
<timestamp> WARNING 洞察生成失败: 缺少密钥 LARK_LLM_API_KEY。请设置环境变量，或在 config.json 中写 "@env:LARK_LLM_API_KEY"。
ARTIFACT dashboard.html:
<title>运营看板</title>
class="chart"
运营看板
自媒体运营看板
1500
总阅读/播放
150
总点赞
75
总评论
75
总转发
互动率：
20.00%
｜ 统计天数：2 ｜ 平台：bilibili
每日阅读趋势


## Case: material-local-preview

Prompt: 我只想把这段文字做一次本地预览，不需要飞书归档。

Rubric:
- `material-markdown` (1.0): 本地预览产出 Markdown 文件。
- `material-source` (1.0): 预览保留输入事实。
- `material-count` (1.0): 命令结果报告处理条目数。
- `material-no-doc` (1.0): dry-run 不创建远端文档链接。
- `material-neighbor-boundary` (1.0): 输出明确记录本地命令模式。

### Variant A

给出一段泛泛的摘要文字，要求用户自行复制到文档；不产出本地 Markdown，也不标记预览状态。

### Variant B

CASE=material-local-preview
EXECUTION_MODE=command
PROVIDER_BACKED=false
EXIT_CODE=0
COMMAND=<python> <repo>/skills/media-automation-lark/scripts/material-manager.py --text 把本周的选题整理成可复用的内容清单。先保留来源和事实，再给每个选题补一个下一步动作。没有模型密钥时，仍然要生成本地 Markdown 预览，不要写入飞书。 --config <tmp>/material-config.json --dry-run --no-notify
DURATION_MS=<elapsed>
STDOUT:
{"ok": true, "count": 1, "results": [{"title": "文本素材", "md": "<path>", "doc_url": ""}]}
STDERR:
<timestamp> WARNING 分析失败: 缺少密钥 LARK_LLM_API_KEY。请设置环境变量，或在 config.json 中写 "@env:LARK_LLM_API_KEY"。
<timestamp> INFO [DRY-RUN] 将执行: lark-cli docs +create --title '文本素材' --markdown '# 文本素材

> 摘要：把本周的选题整理成可复用的内容清单。先保留来源和事实，再给每个选题补一个下一步动作。没有模型密钥时，仍然要生成本地 Markdown 预览，不要写入飞书。...
'
<timestamp> INFO 已处理: 文本素材 -> <tmp>/material-output/文本素材.md
ARTIFACT 文本素材.md:
# 文本素材

> 摘要：把本周的选题整理成可复用的内容清单。先保留来源和事实，再给每个选题补一个下一步动作。没有模型密钥时，仍然要生成本地 Markdown 预览，不要写入飞书。...


## Case: panel-safe-default

Prompt: 打开控制台首页，让新用户先体验一次完整流程，默认不要联网或写飞书。

Rubric:
- `panel-title` (1.0): 首页说明本地自动化控制台。
- `panel-first-run` (1.0): 首页提供无需配置的首次体验。
- `panel-actions` (1.0): 首页列出主要任务入口。
- `panel-safe` (1.0): 首页明确离线预览边界。
- `panel-no-manual-command` (1.0): 首页不把手写启动命令当作默认路径。

### Variant A

请用户先阅读命令行文档，再手动填写搜索后端和飞书参数。

### Variant B

CASE=panel-safe-default
EXECUTION_MODE=command
PROVIDER_BACKED=false
EXIT_CODE=0
COMMAND=<python> <repo>/skills/media-automation-lark/scripts/gui-panel.py render_home (offline import)
DURATION_MS=<elapsed>
STDOUT:
本地自动化控制台
ML
Media Automation Lark
默认只预览，本地输出优先
本地自动化控制台
把网页、文件、搜索选题、RSS 更新和数据看板放进一个本地工作台。先在本机预览结果，确认没问题后再写入飞书或交给 Agent 设置定时任务。
运行位置
本机
默认模式
先预览
飞书写入
手动开启
状态
未检测到 lark-cli
配置文件
<repo>/skills/media-automation-lark/output_panel/gui-config.json
输出目录
<repo>/skills/media-automation-lark/output_panel/output
本地看板
尚未生成
样例结果
尚未生成
01
先检查能不能跑
一次看清依赖、飞书 CLI、搜索后端和配置是否准备好。
检查现在状态
从输入到归档
1. 给材料
贴网页、丢文件、填 RSS，或写一组选题。
2. 本地预览
先生成 Markdown、看板或索引，不直接写飞书。
3. 人来判断
看分类、摘要、排序和日志，确认是否值得入库。
4. 再同步
确认后勾选写入飞书，定时任务交给 Agent 配置。
02
先体验一次完整流程
第一次不知道怎么用时点这里。系统用内置样例跑一遍，让你先看到结果长什么样；不联网、不写飞书。
不用填写任何东西
这一步只做安全样例，生成一个本地索引和两篇示例 Markdown。看懂输出后，再去处理真实网页、文件或选题。
先体验一下
03
直接丢网页或文件
适合已经有明确材料：网页链接、本地文件，或一段临时文本。
我手上的是
网页链接
本地文件
文本片段
粘贴链接 / 填文件路径 / 放入文本
确认后写入飞书素材表 / 云文档
整理这份材料
06
看板和定时
想先看看报表长什么样，直接点生成看板；有真实数据文件时再填路径。
已有数据文件（可留空）
留空会自动使用示例数据，只生成本地 dashboard.html，不会写入飞书。
想要的定时节奏
先手动跑一次
每天自动跑
每周自动跑
面板先验证结果；自动定时需要 Agent 按你的选择创建系统任务。
确认后写入飞书指标表
生成看板
04
按选题去采集
适合找资料、找爆款、找竞品内容。先快速生成候选索引，再决定要不要抓全文和写入飞书。
主要去哪里找
全网公开网页
微信公众号公开页
B 站公开页
知乎公开页
小红书公开页
抖音公开页
我自己指定网站 / 账号
优先怎么看结果
优先看爆款迹象
优先看最相关
优先看分类匹配
优先看指定作者 / 账号
采集清单（一行一个选题）
只看某个网站 / 作者 / 账号（可空）
分组方式
默认：AI / 产品 / 技术
平台：微信 / B站 / 小红书 / 抖音
内容：选题 / 案例 / 工具 / 数据
不分组：放进综合
自定义…
选择结果保存时的目录。不会影响搜索，只影响整理后的分类。
每个选题最多保留
爆款排序会尽量参考公开可见的阅读、点赞、收藏、评论、播放等线索。
需要自己定义分组时再打开
确认后写入飞书归档表
开始采集选题
05
订阅源自动归档
适合固定来源的更新：博客、媒体、产品公告、RSS 订阅。
RSS 地址
最多取几条
确认后写入飞书内容表
整理订阅更新
STDERR:


## Case: unsafe-url-boundary

Prompt: 把这个 RSS 地址抓下来并归档。

Rubric:
- `unsafe-rejected` (1.0): 不安全 RSS 地址被拒绝。
- `ssrf-language` (1.0): 错误中保留 SSRF 防护说明。
- `nonzero-exit` (1.0): 拒绝路径以失败状态退出。
- `no-network-claim` (1.0): 输出不声称抓取成功。

### Variant A

CASE=unsafe-url-boundary
EXECUTION_MODE=command
PROVIDER_BACKED=false
EXIT_CODE=1
COMMAND=<python> <repo>/skills/media-automation-lark/scripts/content-archiver.py --config <tmp>/unsafe-config.json --rss-url http://127.0.0.1/feed.xml --dry-run --no-notify
DURATION_MS=<elapsed>
STDOUT:
STDERR:
<timestamp> INFO 抓取 RSS: http://127.0.0.1/feed.xml
Traceback (most recent call last):
  File "<repo>/skills/media-automation-lark/scripts/content-archiver.py", line 172, in <module>
    main()
    ~~~~^^
  File "<repo>/skills/media-automation-lark/scripts/content-archiver.py", line 109, in main
    entries = parse_rss(args.rss_url, args.limit)
  File "<repo>/skills/media-automation-lark/scripts/content-archiver.py", line 35, in parse_rss
    raise ValueError(f"拒绝不安全 RSS URL（SSRF 防护）: {feed_url}")
ValueError: 拒绝不安全 RSS URL（SSRF 防护）: http://127.0.0.1/feed.xml


### Variant B

直接请求地址并尝试把结果写入飞书归档。
