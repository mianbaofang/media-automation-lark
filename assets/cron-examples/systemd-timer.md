# systemd Timer 示例（服务器 / 常驻机适用）

将下面两个文件放到 `/etc/systemd/system/`（或 `~/.config/systemd/user/` 用户级）。

## media-archiver.service

```ini
[Unit]
Description=自媒体内容自动归档到飞书
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=youruser
Environment=PYTHONIOENCODING=utf-8
EnvironmentFile=/etc/media/.env         # 存放 LARK_LLM_API_KEY 等密钥
ExecStart=/usr/bin/python3 /path/to/scripts/content-archiver.py --rss-url "https://example.com/feed.xml"
```

## media-archiver.timer

```ini
[Unit]
Description=每天 23:00 触发归档

[Timer]
OnCalendar=*-*-* 23:00:00
Persistent=true
Unit=media-archiver.service

[Install]
WantedBy=timers.target
```

## 启用

```bash
systemctl daemon-reload
systemctl enable --now media-archiver.timer
systemctl list-timers media-archiver.timer   # 确认已注册
journalctl -u media-archiver.service -e      # 查看运行日志
```

> 每个场景一套 `.service` + `.timer`；`.env` 文件权限设为 `600` 且不纳入版本控制。
