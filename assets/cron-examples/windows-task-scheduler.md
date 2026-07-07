# Windows 任务计划程序（Task Scheduler）示例

> 用户在 Windows（win32）时用本文件；Linux 服务器见同目录 `crontab.txt` / `systemd-timer.md`。

## 1. 用 schtasks 命令行注册（推荐）

以「场景 A 每天 23:00 抓 RSS 归档飞书」为例：

```bat
schtasks /create /tn "MediaArchiver" /tr "python C:\path\to\scripts\content-archiver.py --rss-url https://example.com/feed.xml" /sc daily /st 23:00 /f
```

四个场景：

```bat
:: 场景 A：每天 23:00 内容归档
schtasks /create /tn "MediaArchiver" /tr "python C:\path\scripts\content-archiver.py --rss-url https://example.com/feed.xml" /sc daily /st 23:00 /f

:: 场景 B：每天 08:30 平台数据抓取+看板（--fetch 自动抓，或 --source file.json）
schtasks /create /tn "MediaDataCollector" /tr "python C:\path\scripts\data-collector.py --fetch --push" /sc daily /st 08:30 /f

:: 场景 C：每小时处理素材队列
schtasks /create /tn "MediaMaterial" /tr "python C:\path\scripts\material-manager.py --queue C:\path\queue.json" /sc hourly /st 00:00 /f

:: 场景 D：每天 09:00 搜索采集→分类 Markdown
schtasks /create /tn "MediaCollector" /tr "python C:\path\scripts\collector.py --query \"LLM 应用落地\" --category-map \"AI:大模型,LLM,Agent\"" /sc daily /st 09:00 /f
```

说明：
- `/tn` 任务名；`/sc daily` 每天、`/sc hourly` 每小时；`/st` 开始时间；`/f` 强制覆盖已存在的同名任务。
- `python` 若不在系统 PATH，用完整路径如 `C:\Users\Ethan\.workbuddy\binaries\python\envs\default\Scripts\python.exe`。
- 工作目录默认是 `C:\Windows\System32`，脚本内用绝对路径或 `--config` 指定配置，避免依赖 cwd。

## 2. 环境变量（密钥）

`schtasks` 的 `/tr` 不便注入环境变量。两种方式：

- **推荐**：在 `config.json` 用 `"@env:VAR"` 占位，然后用 `setx` 持久设置用户环境变量：
  ```bat
  setx LARK_LLM_API_KEY "YOUR_LARK_LLM_API_KEY"
  ```
  设置后需新开终端或重启任务才生效（`setx` 只影响此后启动的进程）。
- 或把命令包进一个 `.bat`，在 `.bat` 内 `set VAR=...` 后再 `python ...`，`/tr` 指向该 `.bat`。`.bat` 设权限仅当前用户可读，不纳入版本控制。

## 3. 编码

中文输出防乱码：在 `.bat` 开头加 `set PYTHONIOENCODING=utf-8`，或 `setx PYTHONIOENCODING utf-8`。

## 4. 查看 / 删除 / 手动跑

```bat
schtasks /query /tn "MediaArchiver" /v        :: 查看任务详情
schtasks /run /tn "MediaArchiver"             :: 立即手动触发一次
schtasks /delete /tn "MediaArchiver" /f       :: 删除任务
```

## 5. 用图形界面（taskschd.msc）

`Win+R` 输入 `taskschd.msc` 打开图形界面，可创建基本任务、查看运行历史与上次结果码。非零退出码会在历史里标"上次运行结果"。

> 日志：脚本进度走 stderr、结构化结果走 stdout，建议在 `.bat` 末尾重定向：
> `python ... >> D:\logs\media.log 2>&1`
