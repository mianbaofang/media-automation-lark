# 搜索后端（Search Backends）接入指南

本 skill 的「采集」能力不绑定任何单一搜索工具，而是定义一组**可插拔后端**。
核心理念：**装了就用，没装就跳过，绝不让整个 skill 崩溃。**

---

## 1. 后端清单

| 名称 | 类型 | 调用方式 | 需要密钥 | 脚本可用 | GitHub / 安装 |
|------|------|----------|----------|----------|----------------|
| `anysearch` | 搜索 + 抓取 | `python anysearch_cli.py search/extract` | 否（匿名可用） | ✓ | github.com/anysearch-ai/anysearch-skill |
| `tavily` | 搜索 + 抓取 | `tvly search/extract --json` | 是（TAVILY_API_KEY） | ✓ | cli.tavily.com/install.sh |
| `autocli` | 抓取（read→Markdown） | `autocli read <url> -f markdown` | 否（复用 Chrome 登录态） | ✓ | github.com/nashsu/AutoCLI |
| `agent_reach` | 搜索（15 平台） | `agent-reach doctor` / `mcporter` | 否 | ✗ 仅交互 | github.com/Panniantong/Agent-Reach |
| `multi_search` | 搜索（17 引擎） | 依赖 WebFetch 工具 | 否 | ✗ 仅交互 | 技能市场安装 |
| `http` | 抓取（兜底） | requests + BeautifulSoup | 否 | ✓ | 内置，无需安装 |

- **脚本可用**：能否被 `collector.py` 在定时任务（无头）中直接调用。
- `agent_reach` / `multi_search` 只能在**交互模式**由 agent 编排（对话里调用对应 skill 或 WebFetch），不进无头脚本。

---

## 2. 运行时检测逻辑

`scripts/search_backends.py` 在每次运行自动检测：

1. 在以下目录查找后端 skill（`SKILL.md` 存在即视为已装）：
   - `$SKILLS_ROOT` 环境变量
   - `~/.workbuddy/skills`
   - `~/.agents/skills`
   - `~/.claude/skills`
   - 本 skill 的上级目录
2. 对二进制类后端（`tvly` / `autocli`）用 `which` 检测。
3. 对需要登录态的（`tavily`）额外跑 `--status` 确认已鉴权。

`collector.py` 启动时打印检测表：
- `✓` 已装且可用
- `○` 已装但未鉴权（如 tavily 未 login）
- `✗` 未安装

**降级规则**：没有任何可用搜索后端、也没给 RSS 源时，`collector.py` 直接给出安装命令并以退出码 2 结束（不静默失败、不崩溃）。

---

## 3. 安装时下载（解决「没装就废了」）

初次安装本 skill 时，运行：

```bash
# 方式一：env-check 一并处理（推荐）
python3 scripts/env-check.py --auto-install

# 方式二：单独拉取搜索后端
python3 scripts/install_backends.py --all
python3 scripts/install_backends.py anysearch tavily   # 只装指定
python3 scripts/install_backends.py --all --dry-run     # 先看会做什么
```

`install_backends.py` 行为：
- 已装的自动跳过（幂等），`--force` 可强制重拉。
- `anysearch` / `agent_reach`：`git clone --depth 1` 到技能根目录。
- `tavily` / `autocli`：打印官方安装脚本（curl 管道执行需用户确认，不静默执行远程脚本）。
- `multi_search`：提示通过技能市场安装。
- 完成后回显检测状态。

> 注意：`tavily` 克隆/安装后仍需 `tvly login` 或设置 `TAVILY_API_KEY`；
> `autocli` 需要本机 Chrome 已登录目标站点。`anysearch` 匿名即可用，优先级最高。

---

## 4. collector.py 如何使用后端

采集流程（`scripts/collector.py`，场景 D）：

```
用户 query
   └─> 遍历可用 SEARCH 后端（anysearch → tavily）→ 收集候选 URL（去重）
        └─> 遍历可用 FETCH 后端（autocli → anysearch → tavily → http 兜底）→ 取 Markdown 正文
             └─> 按 category_map 分类 → 写 <output_dir>/<分类>/<日期>-<标题>.md
                  └─> 生成 index.md；可选归档飞书多维表格
```

分类规则（`config.json` 的 `search.category_map`，或用 `--category-map`）：
```
"AI:大模型,LLM,Agent;产品:增长,PM,运营;技术:Python,架构,RAG"
```
匹配标题/URL/检索词中的关键词；都不命中则归入 `default_category`（默认 `综合`）。

---

## 5. 常见组合建议

- **零配置最快上手**：只装 `anysearch`（免 key），即可搜索 + 抓取，无需任何平台账号。
- **中文内容 + 登录态平台**：加 `autocli`（读微信/知乎/小红书等登录态页面出 Markdown）。
- **高质量英文检索**：加 `tavily`（需 key）。
- **交互模式全平台调研**：对话里直接让我用 `agent-reach` / `multi-search-engine`，由我编排，不走无头脚本。
