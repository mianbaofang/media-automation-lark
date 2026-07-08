#!/usr/bin/env python3
"""Agent-facing launcher for the local control panel.

Users should not have to type shell commands. Agent runtimes can call this
script to start, stop, or inspect the local panel and then show the URL.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PANEL_DIR = ROOT / "output_panel"
PID_FILE = PANEL_DIR / "panel.pid"
LOG_FILE = PANEL_DIR / "panel.log"
ERR_FILE = PANEL_DIR / "panel.err.log"
LAUNCHER_FILE = PANEL_DIR / "panel-launch.cmd"


def is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def pid_for_port(port: int) -> int | None:
    if os.name != "nt":
        return None
    try:
        proc = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    suffix = f":{port}"
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[1].endswith(suffix) and parts[3].upper() == "LISTENING":
            try:
                return int(parts[4])
            except ValueError:
                return None
    return None


def terminate_pid(pid: int) -> tuple[bool, str]:
    if os.name == "nt":
        proc = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.returncode == 0, (proc.stderr or proc.stdout).strip()
    try:
        os.kill(pid, signal.SIGTERM)
        return True, ""
    except OSError as exc:
        return False, str(exc)


def payload(status: str, host: str, port: int, pid: int | None = None, message: str = "") -> dict:
    return {
        "ok": status in {"running", "started", "stopped"},
        "status": status,
        "url": f"http://{host}:{port}",
        "pid": pid,
        "log": str(LOG_FILE),
        "error_log": str(ERR_FILE),
        "message": message,
    }


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def start_windows_process(host: str, port: int) -> int:
    LAUNCHER_FILE.write_text(
        "\r\n".join(
            [
                "@echo off",
                f'cd /d "{ROOT}"',
                (
                    f'"{sys.executable}" "{ROOT / "scripts" / "gui-panel.py"}" '
                    f'--host "{host}" --port "{port}" '
                    f'>> "{LOG_FILE}" 2>> "{ERR_FILE}"'
                ),
            ]
        )
        + "\r\n",
        encoding="utf-8",
    )
    script = (
        "$ErrorActionPreference = 'Stop'; "
        f"$p = Start-Process -FilePath {ps_quote(str(LAUNCHER_FILE))} "
        f"-WorkingDirectory {ps_quote(str(ROOT))} "
        "-WindowStyle Hidden "
        "-PassThru; "
        "[Console]::Out.Write($p.Id)"
    )
    proc = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "Start-Process failed").strip())
    return int(proc.stdout.strip())


def start_posix_process(host: str, port: int) -> int:
    cmd = [sys.executable, str(ROOT / "scripts" / "gui-panel.py"), "--host", host, "--port", str(port)]
    with LOG_FILE.open("a", encoding="utf-8") as log, ERR_FILE.open("a", encoding="utf-8") as err:
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=log,
            stderr=err,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
    return proc.pid


def start(host: str, port: int, open_browser: bool) -> dict:
    PANEL_DIR.mkdir(parents=True, exist_ok=True)
    pid = read_pid()
    port_pid = pid_for_port(port) if is_port_open(host, port) else None
    if port_pid:
        if open_browser:
            webbrowser.open(f"http://{host}:{port}")
        return payload("running", host, port, port_pid, "Panel is already running.")

    try:
        new_pid = start_windows_process(host, port) if os.name == "nt" else start_posix_process(host, port)
    except Exception as exc:  # noqa: BLE001
        return payload("error", host, port, None, str(exc))
    ready = False
    for _ in range(20):
        if is_port_open(host, port):
            ready = True
            break
        time.sleep(0.2)
    if not ready:
        return payload("error", host, port, new_pid, "Panel did not answer. Check the log files.")
    time.sleep(0.3)
    actual_pid = pid_for_port(port) or new_pid
    if not is_port_open(host, port):
        return payload("error", host, port, new_pid, "Panel exited after startup. Check the log files.")
    PID_FILE.write_text(str(actual_pid), encoding="utf-8")
    if open_browser:
        webbrowser.open(f"http://{host}:{port}")
    return payload("started", host, port, actual_pid, "Panel started.")


def stop(host: str, port: int) -> dict:
    pid = read_pid()
    active_pid = pid_for_port(port)
    if not active_pid:
        return payload("stopped", host, port, pid, "Panel was not running.")
    ok, message = terminate_pid(active_pid)
    if not ok:
        return payload("error", host, port, active_pid, message)
    try:
        PID_FILE.unlink()
    except OSError:
        pass
    return payload("stopped", host, port, active_pid, "Panel stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent launcher for Media Automation Lark control panel")
    parser.add_argument("action", choices=["start", "stop", "status"], nargs="?", default="start")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--open", action="store_true", help="Ask OS to open the panel URL")
    args = parser.parse_args()

    if args.action == "start":
        result = start(args.host, args.port, args.open)
    elif args.action == "stop":
        result = stop(args.host, args.port)
    else:
        port_pid = pid_for_port(args.port) if is_port_open(args.host, args.port) else None
        result = payload(
            "running" if port_pid else "stopped",
            args.host,
            args.port,
            port_pid,
        )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
