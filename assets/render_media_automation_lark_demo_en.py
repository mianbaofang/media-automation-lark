"""Render the English README preview from the canonical HyperFrames timeline.

The source timeline remains the single visual baseline. This renderer applies
the English copy at render time so the Chinese and English cuts keep the same
scene order, pacing, images, and layout.
"""

from __future__ import annotations

import argparse
import base64
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hyperframes" / "media-automation-lark-timeline" / "index.html"
DEFAULT_OUTPUT = ROOT / "assets" / "media-automation-lark-demo.en.gif"
GSAP_URL = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"
GSAP_CACHE = ROOT / "assets" / "gsap-3.14.2.min.js"
PLAYWRIGHT_TIMEOUT_MS = 15_000
DEFAULT_BROWSER_TIMEOUT_SECONDS = 120.0
FFMPEG_TIMEOUT_SECONDS = 120.0
PROCESS_STARTED = time.monotonic()


def log(message: str) -> None:
    elapsed = time.monotonic() - PROCESS_STARTED
    print(f"[media-automation-lark.en +{elapsed:6.1f}s] {message}", flush=True)


# Exact text replacements keep layout and animation code untouched.
TRANSLATIONS = {
    "<html lang=\"zh-CN\">": "<html lang=\"en\">",
    "<title>Media Automation Lark Skill Flow</title>": "<title>Media Automation Lark Product Preview</title>",
    "内容运营最贵的，不是工具": "The real cost is not the tool",
    "贵在每天": "The real cost",
    "反复搬运": "is repeated handoffs",
    "网页、搜索结果、素材文件、平台数据来回复制。真正被吃掉的，是选题判断和复盘时间。": (
        "Web pages, search results, files, and metrics get copied back and forth. "
        "What disappears is the time to choose well and learn from the numbers."
    ),
    "少复制": "Less copying",
    "少漏项": "Fewer misses",
    "少等人": "Less waiting",
    "多留痕": "More traceability",
    "先把输入接住": "Capture inputs first",
    "文章、素材、指标先进统一流程，再决定写入飞书还是只保留本地结果。": (
        "Articles, assets, and metrics enter one flow; then choose whether to write "
        "to Lark or keep the result local."
    ),
    "一次运行，先做检查": "One run, then a check",
    "别让人等脚本": "Do not make people wait",
    "脚本先自查": "Check before it runs",
    "依赖、搜索后端、飞书授权先检查，缺什么直接提示。": (
        "Check dependencies, search backends, and Lark access first; show what is missing."
    ),
    "能先预演的步骤先预演，避免把错误结果写进团队空间。": (
        "Preview what can be previewed before writing anything to the team space."
    ),
    "本地结果先生成，用户确认后再同步到飞书。": (
        "Generate locally first. Sync to Lark only after confirmation."
    ),
    "四个高频场景": "Four everyday use cases",
    "把日常琐事": "Turn daily chores",
    "变成固定按钮": "into fixed buttons",
    "内容归档": "Content archive",
    "新文章自动进表，不靠手工登记": "New posts enter the table automatically",
    "数据看板": "Metrics dashboard",
    "指标当天汇总，复盘不用等周报": "Same-day rollups for faster review",
    "素材整理": "Asset library",
    "文件转成可搜索、可复用的素材": "Files become searchable and reusable",
    "搜索采集": "Search capture",
    "链接变资料包，选题有出处": "Links become sourced research packs",
    "少切工具，少丢上下文": "Fewer tool switches",
    "同一批输入，从采集到归档走同一条线，后面查得到。": (
        "One input stream from capture to archive, with context you can find later."
    ),
    "链接只是起点": "A link is only the start",
    "真正有用的是正文、分类、摘要和可以复查的来源。": (
        "The useful part is the text, structure, summary, and source you can revisit."
    ),
    "选题研究少走回头路": "Research without the round trip",
    "搜索结果": "Search results",
    "直接变资料包": "become research packs",
    "按关键词抓正文，重复页面会被过滤。": (
        "Fetch the main text by keyword and filter duplicate pages."
    ),
    "结果按主题分组，自动生成索引。": "Group results by topic and build an index automatically.",
    "写作、复盘、团队共享都从同一份资料开始。": (
        "Start writing, reviewing, and sharing from the same source pack."
    ),
    "素材不该只躺在文件夹里": "Assets should not sleep in folders",
    "旧素材": "Make old assets",
    "重新变值钱": "useful again",
    "PDF、Office、网页和图片统一转成可读内容。": (
        "Turn PDFs, Office files, web pages, and images into readable content."
    ),
    "摘要、标签、行动项自动补齐。": "Fill in summaries, tags, and action items automatically.",
    "下一次选题时，不用重新翻一遍文件夹。": (
        "Reuse the material next time instead of searching the folder again."
    ),
    "素材开始产生复利": "Assets start to compound",
    "一次整理，后面的选题、脚本、复盘都能继续用。": (
        "Organize once, then reuse the material for ideas, scripts, and review."
    ),
    "先看到趋势": "See the signal sooner",
    "看板不等人工整理，数据先变成能讨论的画面。": (
        "The dashboard turns raw numbers into a picture the team can discuss."
    ),
    "复盘越快，调整越早": "Faster review, earlier changes",
    "当天看数据": "See today's numbers",
    "当天调内容": "Adjust today's content",
    "阅读、互动、涨粉数据集中看。": "Bring reads, engagement, and follower growth into one view.",
    "互动率、趋势和平台分布自动计算。": (
        "Calculate engagement rate, trends, and platform mix automatically."
    ),
    "需要时推送到飞书群，减少反复问数。": (
        "Push to a Lark group when needed and stop chasing numbers."
    ),
    "自动化也要让人安心": "Automation should still feel safe",
    "先预览": "Preview first",
    "再同步": "Sync second",
    "不安全地址不请求，减少误触和异常结果。": (
        "Do not request unsafe URLs; reduce accidental calls and bad results."
    ),
    "采集、解析、写入分开执行，哪一步失败一眼能看出。": (
        "Keep capture, parsing, and writing separate so failures are visible."
    ),
    "先看本地预览，再决定要不要写进飞书。": (
        "Review the local preview before deciding whether to write to Lark."
    ),
    "少一点惊吓": "A little less surprise",
    "自动化不是黑盒，用户要能随时知道它跑到哪一步。": (
        "Automation is not a black box; people should always see where it is."
    ),
    "人只看结果": "People see the result",
    "资料、素材、指标和通知都沉到飞书，团队不用追问文件在哪。": (
        "Research, assets, metrics, and notices land in Lark so no one has to ask where the file went."
    ),
    "把时间还给判断": "Give time back to judgment",
    "少做搬运": "Do less busywork",
    "多做决策": "Make more decisions",
    "资料包": "Research packs",
    "素材摘要": "Asset briefs",
    "指标看板": "Metric boards",
    "飞书通知": "Lark alerts",
    "本地留底": "Local copy",
    "新人能接手，老素材能复用，负责人不用等人整理。省下来的时间，才是这个工具的价值。": (
        "New teammates can take over, old assets keep working, and owners stop waiting for manual cleanup. "
        "The time saved is the product."
    ),
}


# The authored GSAP timeline is useful for interactive playback, but its
# time setter can block Chromium during headless capture. Keep capture
# deterministic by applying the same short entrance/fade timings directly.
MANUAL_RENDERER_SCRIPT = r'''<script>
(() => {
  const clamp = (value) => Math.max(0, Math.min(1, value));
  const easeOut = (value, power) => 1 - Math.pow(1 - clamp(value), power);
  const sceneLength = 4.5;
  const fadeStart = 4.28;

  const setStyle = (element, opacity, y, scale = 1) => {
    element.style.opacity = String(opacity);
    element.style.transform = `translateY(${y}px) scale(${scale})`;
  };

  const animate = (elements, localTime, start, duration, fromY, fromOpacity, stagger, power) => {
    elements.forEach((element, index) => {
      const progress = easeOut((localTime - start - index * stagger) / duration, power);
      setStyle(
        element,
        fromOpacity + (1 - fromOpacity) * progress,
        fromY * (1 - progress),
      );
    });
  };

  window.__manualRenderAt = (time) => {
    const scenes = Array.from(document.querySelectorAll('.scene'));
    scenes.forEach((scene, index) => {
      const localTime = time - index * sceneLength;
      const active = localTime >= 0 && localTime <= sceneLength;
      const sceneOpacity = !active
        ? 0
        : localTime >= fadeStart
          ? 1 - clamp((localTime - fadeStart) / (sceneLength - fadeStart))
          : 1;
      scene.style.opacity = String(sceneOpacity);
      scene.querySelectorAll('h1, h2, .lead, .chips, .image-card, .kicker, .overlay-panel, .terminal, .flow-grid, .flow-card, .bullets, .bullet, .chip, .step').forEach((element) => {
        setStyle(element, 0, 0);
      });
      if (!active) return;

      const headings = Array.from(scene.querySelectorAll('h1, h2'));
      const leadGroups = Array.from(scene.querySelectorAll('.lead, .chips, .bullets, .flow-grid'));
      const images = Array.from(scene.querySelectorAll('.image-card'));
      const kickers = Array.from(scene.querySelectorAll('.kicker'));
      const overlays = Array.from(scene.querySelectorAll('.overlay-panel, .terminal, .flow-card, .bullet, .chip'));
      const steps = Array.from(scene.querySelectorAll('.step'));

      if (index === 0) {
        headings.forEach((element) => setStyle(element, 1, 0));
        scene.querySelectorAll('.lead, .chips, .image-card').forEach((element) => setStyle(element, 1, 0));
      } else {
        animate(headings, localTime, 0.18, 0.62, 48, 0, 0, 3);
        animate(leadGroups, localTime, 0.46, 0.58, 28, 0, 0, 3);
        images.forEach((element) => {
          const progress = easeOut((localTime - 0.34) / 0.68, 3);
          setStyle(element, progress, 34 * (1 - progress), 0.985 + 0.015 * progress);
        });
      }

      animate(kickers, localTime, 0.08, 0.46, 20, 0, 0, 2);
      animate(overlays, localTime, 0.76, 0.42, 18, 0, 0.035, 2);
      animate(steps, localTime, 0.1, 0.32, 12, 0.45, 0.014, 2);
    });
  };
})();
</script>'''


def translated_source() -> str:
    source = SOURCE.read_text(encoding="utf-8")
    for original, translated in TRANSLATIONS.items():
        if original not in source:
            raise ValueError(f"Source text not found: {original}")
        source = source.replace(original, translated)
    source = source.replace(
        'src="assets/',
        f'src="{SOURCE.parent.as_uri()}/assets/',
    )
    # The GIF has no audio track. Removing the media element from the render
    # copy prevents Chromium from waiting on file:// audio metadata.
    source = re.sub(r"\s*<audio\b[^>]*>.*?</audio>", "", source, flags=re.DOTALL)
    if GSAP_CACHE.exists():
        gsap = GSAP_CACHE.read_text(encoding="utf-8")
    else:
        with urllib.request.urlopen(GSAP_URL, timeout=30) as response:
            gsap = response.read().decode("utf-8")
    source = source.replace(
        '<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>',
        f"<script>{gsap}</script>",
    )
    source = source.replace("</body>", f"{MANUAL_RENDERER_SCRIPT}\n</body>")
    if re.search(r"[\u3400-\u9fff]", source):
        raise ValueError("Translated source still contains CJK characters")
    return source


def _render_frames_worker(html_path: Path, frames_dir: Path, frame_count: int) -> None:
    log(f"browser worker started: frames={frame_count}")
    frames_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = None
        context = None
        try:
            log(f"browser runtime ready: {playwright.chromium.executable_path}")
            log("browser launch: start")
            browser = playwright.chromium.launch(
                headless=True,
                timeout=PLAYWRIGHT_TIMEOUT_MS,
                args=[
                    "--disable-gpu",
                    "--no-sandbox",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            log("browser launch: complete")
            context = browser.new_context(
                viewport={"width": 960, "height": 540},
                device_scale_factor=1,
            )
            page = context.new_page()
            page.set_default_timeout(PLAYWRIGHT_TIMEOUT_MS)
            log("page created")

            # The composition is authored at 1920x1080, but the deliverable is
            # 960x540. Scale the fixed canvas in the page so Playwright captures
            # the final raster size directly instead of encoding four times as
            # many pixels and downscaling every frame in FFmpeg.
            log("page.goto: start")
            page.goto(
                html_path.as_uri(),
                wait_until="domcontentloaded",
                timeout=PLAYWRIGHT_TIMEOUT_MS,
            )
            log("page.goto: complete")
            log("document settle: start")
            page.wait_for_timeout(500)
            log("document settle: complete")
            log("scale stylesheet: start")
            page.add_style_tag(
                content=(
                    "html, body { width: 960px !important; height: 540px !important; "
                    "overflow: hidden !important; } "
                    "#root { transform: scale(0.5); transform-origin: 0 0; }"
                ),
            )
            log("scale stylesheet: complete")
            ready = page.evaluate("typeof window.__manualRenderAt === 'function'")
            log(f"manual renderer ready: {ready}")
            if not ready:
                raise RuntimeError("The manual renderer did not initialize")
            page.evaluate("window.__manualRenderAt(0)")
            log("manual renderer initialized")
            cdp = context.new_cdp_session(page)
            log("CDP screenshot session ready")
            for frame in range(frame_count):
                time_position = frame / 5
                if frame == 0:
                    log("manual frame state: start")
                page.evaluate(
                    "timePosition => window.__manualRenderAt(timePosition)",
                    time_position,
                )
                if frame == 0:
                    log("manual frame state: complete")
                screenshot = cdp.send(
                    "Page.captureScreenshot",
                    {
                        "format": "png",
                        "fromSurface": True,
                        "captureBeyondViewport": False,
                    },
                )
                (frames_dir / f"frame-{frame:03d}.png").write_bytes(
                    base64.b64decode(screenshot["data"])
                )
                if frame == 0 or (frame + 1) % 30 == 0 or frame == frame_count - 1:
                    log(f"frame {frame + 1}/{frame_count} written")
        finally:
            if context is not None:
                log("browser context close: start")
                context.close()
                log("browser context close: complete")
            if browser is not None:
                log("browser close: start")
                browser.close()
                log("browser close: complete")


def _forward_worker_output(stream) -> None:
    for line in iter(stream.readline, ""):
        if line:
            print(line.rstrip("\r\n"), flush=True)
    stream.close()


def _terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        process.kill()


def render_frames(
    html_path: Path,
    frames_dir: Path,
    frame_count: int,
    browser_timeout_seconds: float,
) -> None:
    """Run browser capture in a killable child process with a hard deadline."""
    command = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "--_frames-worker",
        "--_html",
        str(html_path),
        "--_frames-dir",
        str(frames_dir),
        "--_frame-count",
        str(frame_count),
    ]
    log(f"browser worker process start (hard timeout {browser_timeout_seconds:.1f}s)")
    process = subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    if process.stdout is None:
        raise RuntimeError("Failed to capture browser worker logs")
    output_thread = threading.Thread(
        target=_forward_worker_output,
        args=(process.stdout,),
        daemon=True,
    )
    output_thread.start()
    deadline = time.monotonic() + browser_timeout_seconds
    while process.poll() is None:
        if time.monotonic() >= deadline:
            log("browser worker hard timeout reached; terminating its process tree")
            _terminate_process_tree(process)
            output_thread.join(timeout=2)
            raise TimeoutError(
                f"Browser rendering exceeded {browser_timeout_seconds:.1f}s"
            )
        time.sleep(0.2)
    output_thread.join(timeout=2)
    if process.returncode != 0:
        raise RuntimeError(
            f"Browser worker failed with exit code {process.returncode}"
        )
    log("browser worker process complete")


def make_gif(frames_dir: Path, output: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    palette = frames_dir / "palette.png"
    log("ffmpeg palette pass: start")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            "5",
            "-i",
            str(frames_dir / "frame-%03d.png"),
            "-vf",
            "palettegen=max_colors=192:reserve_transparent=0",
            str(palette),
        ],
        check=True,
        timeout=FFMPEG_TIMEOUT_SECONDS,
    )
    log("ffmpeg palette pass: complete")
    log("ffmpeg GIF pass: start")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            "5",
            "-i",
            str(frames_dir / "frame-%03d.png"),
            "-i",
            str(palette),
            "-lavfi",
            "[0:v][1:v]paletteuse=dither=sierra2_4a",
            "-loop",
            "0",
            str(output),
        ],
        check=True,
        timeout=FFMPEG_TIMEOUT_SECONDS,
    )
    log(f"ffmpeg GIF pass: complete ({output})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frames", type=int, default=180)
    parser.add_argument(
        "--browser-timeout",
        type=float,
        default=DEFAULT_BROWSER_TIMEOUT_SECONDS,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--_frames-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_html", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--_frames-dir", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--_frame-count", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("--frames must be positive")
    if args.browser_timeout <= 0:
        parser.error("--browser-timeout must be positive")
    if args._frames_worker:
        if not args._html or not args._frames_dir or not args._frame_count:
            parser.error("worker arguments are incomplete")
        _render_frames_worker(args._html, args._frames_dir, args._frame_count)
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    log(f"translation start: {SOURCE}")
    with tempfile.TemporaryDirectory(prefix="media-automation-lark-en-") as temp:
        temp_dir = Path(temp)
        html_path = temp_dir / "index.html"
        html_path.write_text(translated_source(), encoding="utf-8")
        log(f"translated HTML ready: {html_path}")
        render_frames(
            html_path,
            temp_dir,
            args.frames,
            args.browser_timeout,
        )
        make_gif(temp_dir, args.output)
    log(f"render complete: {args.output}")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
