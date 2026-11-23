"""把 docs/screenshots/*.md 的真實 OpenCode 輸出轉成終端機風格 SVG，給 README 用。"""
import re
import sys
from pathlib import Path

import unicodedata
from html import escape

ROOT = Path(__file__).resolve().parent.parent
SRC, DST = ROOT / "docs/screenshots", ROOT / "docs/images"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def clean(name, start=None, max_lines=40):
    lines = [l.rstrip() for l in ANSI.sub("", (SRC / name).read_text()).splitlines()]
    lines = [l for l in lines if l.strip()]
    if start:
        idx = next((i for i, l in enumerate(lines) if start in l), 0)
        lines = lines[:2] + ["   ⋯（略過中間步驟）⋯"] + lines[idx:]
    if len(lines) > max_lines:
        lines = lines[:max_lines] + ["   ⋯（完整內容見 docs/screenshots/）⋯"]
    return lines


COLORS = {"title": "#f0c674", "tool": "#81a2be", "dim": "#707880", "head": "#b5bd68", "text": "#e6e6e6"}
WRAP = 92  # 顯示寬度（中文算 2）


def width(ch):
    return 2 if unicodedata.east_asian_width(ch) in "WF" else 1


def wrap(line):
    out, cur, w = [], "", 0
    for ch in line:
        if w + width(ch) > WRAP:
            out.append(cur)
            cur, w = "  ", 2
        cur += ch
        w += width(ch)
    return out + [cur]


def style(l):
    if l.startswith("### "):
        return "title"
    if l.startswith("⚙"):
        return "tool"
    if l.startswith(("✗", "✱", "→", ">", "   ⋯")):
        return "dim"
    if l.startswith("## "):
        return "head"
    return "text"


def render(name, out, title, **kw):
    rows = []
    for l in clean(name, **kw):
        st = style(l)
        rows += [(st, part) for part in wrap(l)]
    lh, top, w = 22, 56, 900
    h = top + lh * len(rows) + 20
    body = "\n".join(
        f'<text x="20" y="{top + i * lh}" fill="{COLORS[st]}"{" font-weight=\"bold\"" if st in ("title", "tool", "head") else ""}>{escape(t)}</text>'
        for i, (st, t) in enumerate(rows))
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<rect width="{w}" height="{h}" rx="10" fill="#1d1f21"/>
<circle cx="22" cy="20" r="6" fill="#ff5f56"/><circle cx="42" cy="20" r="6" fill="#ffbd2e"/><circle cx="62" cy="20" r="6" fill="#27c93f"/>
<text x="{w // 2}" y="25" fill="#c5c8c6" font-size="14" text-anchor="middle" font-family="sans-serif">{escape(title)}</text>
<g font-family="Consolas, 'Noto Sans Mono CJK TC', 'Microsoft JhengHei', monospace" font-size="15" xml:space="preserve">
{body}
</g></svg>"""
    (DST / out).write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    render("q1.md", "q1.svg", "Q1 現在顯卡被誰佔用？")
    render("q2.md", "q2.svg", "Q2 我還能再載入一個 27B 的模型嗎？")
    render("q3_before.md", "q3_before.svg", "Q3 改前：模型自己推論 → 答錯", max_lines=24)
    render("q3.md", "q3_after.svg", "Q3 改後：引用程式判斷的 compatibility → 答對")
    render("q4.md", "q4.svg", "Q4 完整環境健檢報告", start="## 一句話總結", max_lines=60)
    print("ok", file=sys.stderr)
