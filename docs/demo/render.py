"""Record the README demo GIF from a real run.

Runs the two demo steps against a live SafeExec, captures their real output and
renders it as an animated terminal GIF with Pillow. No terminal recorder needed.

    docker compose up --build -d
    uv run --with pillow python docs/demo/render.py   # writes docs/demo/demo.gif
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name("demo.gif")
API = "http://localhost:8000/v1/executions"

# Look
COLS, ROWS = 92, 30
FONT_SIZE = 15
PAD = 18
BAR = 30
BG = (30, 30, 46)
BAR_BG = (24, 24, 37)
FG = (205, 214, 244)
DIM = (127, 132, 156)
GREEN = (166, 227, 161)
RED = (243, 139, 168)
YELLOW = (249, 226, 175)
BLUE = (137, 180, 250)

# Timing (ms)
TYPE_STEP = 45
LINE_STEP = 70
PAUSE = 1400
END_PAUSE = 4000


def _font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/Library/Fonts/Menlo.ttc",
        "C:/Windows/Fonts/consola.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, FONT_SIZE)
    return ImageFont.load_default()


FONT = _font()
CELL_W = int(FONT.getlength("M"))
CELL_H = FONT_SIZE + 6
WIDTH = PAD * 2 + CELL_W * COLS
HEIGHT = BAR + PAD * 2 + CELL_H * ROWS


def run_timeout_demo() -> list[str]:
    body = json.dumps(
        {"language": "python", "code": "while True: pass", "limits": {"timeout_ms": 1500}}
    ).encode()
    request = urllib.request.Request(API, body, {"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    picked = {k: result[k] for k in ("exit_code", "timed_out", "duration_ms")}
    return json.dumps(picked, indent=2).splitlines()


def run_llm_loop_demo() -> list[str]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "llm_loop.py"), "--offline"],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
        cwd=ROOT,
    )
    return completed.stdout.strip("\n").splitlines()


def color_for(line: str) -> tuple[int, int, int]:
    if line.startswith("#"):
        return DIM
    if line.startswith("==="):
        return BLUE
    if "--- failed" in line or "Error" in line or line.startswith("Traceback"):
        return RED
    if "--- ok" in line or '"timed_out": true' in line:
        return GREEN
    if line.startswith("---"):
        return YELLOW
    return FG


class Terminal:
    def __init__(self) -> None:
        self.lines: list[tuple[str, tuple[int, int, int]]] = []
        self.frames: list[Image.Image] = []
        self.durations: list[int] = []

    def snap(self, duration: int) -> None:
        image = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, WIDTH, BAR), fill=BAR_BG)
        for i, dot in enumerate(((243, 139, 168), (249, 226, 175), (166, 227, 161))):
            x = 16 + i * 20
            draw.ellipse((x, 10, x + 11, 21), fill=dot)
        draw.text((WIDTH // 2 - 60, 7), "safeexec demo", font=FONT, fill=DIM)
        for row, (text, color) in enumerate(self.lines[-ROWS:]):
            y = BAR + PAD + row * CELL_H
            if text.startswith("$ "):
                draw.text((PAD, y), "$", font=FONT, fill=GREEN)
                draw.text((PAD + CELL_W * 2, y), text[2:], font=FONT, fill=FG)
            else:
                draw.text((PAD, y), text, font=FONT, fill=color)
        self.frames.append(image.quantize(colors=64, dither=Image.Dither.NONE))
        self.durations.append(duration)

    def comment(self, text: str) -> None:
        self.lines.append((text, DIM))
        self.snap(PAUSE // 2)

    def type(self, *command_lines: str) -> None:
        for n, part in enumerate(command_lines):
            prefix = "$ " if n == 0 else "    "
            self.lines.append((prefix, FG))
            for end in range(0, len(part) + 1, 3):
                self.lines[-1] = (prefix + part[:end], FG)
                self.snap(TYPE_STEP)
            self.lines[-1] = (prefix + part, FG)
        self.snap(PAUSE // 2)

    def print(self, output: list[str]) -> None:
        for line in output:
            self.lines.append((line[:COLS], color_for(line)))
            self.snap(LINE_STEP)
        self.snap(PAUSE)

    def save(self, path: Path) -> None:
        self.durations[-1] = END_PAUSE
        self.frames[0].save(
            path,
            save_all=True,
            append_images=self.frames[1:],
            duration=self.durations,
            loop=0,
            optimize=True,
        )


def main() -> None:
    timeout_output = run_timeout_demo()
    loop_output = run_llm_loop_demo()

    term = Terminal()
    term.comment("# 1. An infinite loop runs in a single-use container and is killed at the limit")
    term.type(
        "curl -s localhost:8000/v1/executions -H 'content-type: application/json' \\",
        '-d \'{"language":"python","code":"while True: pass","limits":{"timeout_ms":1500}}\' \\',
        "| jq '{exit_code, timed_out, duration_ms}'",
    )
    term.print(timeout_output)
    term.lines.append(("", FG))
    term.comment("# 2. LLM loop: the crash comes back as data and the model fixes its code")
    term.type("uv run -q --group examples python examples/llm_loop.py --offline")
    term.print(loop_output)
    term.save(OUT)
    size_kb = OUT.stat().st_size // 1024
    print(f"wrote {OUT.relative_to(ROOT)} ({size_kb} KB, {len(term.frames)} frames)")


if __name__ == "__main__":
    main()
