#!/usr/bin/env python3
"""Pre-populate the emoji cache with every emoji this project can render.

Sources scanned:
  - scripts/parse_fit.py (static labels such as 📊, 👨‍🏫, the 🚣 hero)
  - every generated ROW_*.md / ERG_*.md (review text is rendered into XHS page 2)
  - a fixed weather set, since weather strings come from the data, not the code

Run: python3 prefetch_emoji.py [--check]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import emoji_source  # noqa: E402

WEATHER = list("☀️ ☁️ ⛅ ☔ 🌧️ 🌦️ 🌤️ 🌥️ ⛈️ ❄️ 🌫️ 🌁 🌈 🌡️ 💨 🌊".split())
REVIEW_MARKERS = list("🌟 ⚡ 🎯 🏆 💪 ✅ ⚠️ 📈 📉 🔥 💤 💡 📊 📋 🚣 👨‍🏫".split())
SOURCE_FILE = HERE / "parse_fit.py"


def is_emoji_char(c: str) -> bool:
    o = ord(c)
    return (
        0x1F300 <= o <= 0x1FAFF
        or 0x1F000 <= o <= 0x1F2FF
        or 0x2600 <= o <= 0x27BF
        or 0x2B00 <= o <= 0x2BFF
        or 0x1F1E6 <= o <= 0x1F1FF
        or o in (0xFE0F, 0x200D, 0x20E3)
        or 0x1F3FB <= o <= 0x1F3FF
    )


def extract(text: str) -> set[str]:
    out, cur = set(), []
    for ch in text:
        if is_emoji_char(ch):
            cur.append(ch)
        else:
            if cur:
                s = "".join(cur).strip("\u200d")
                if s:
                    out.add(s)
                cur = []
    if cur:
        s = "".join(cur).strip("\u200d")
        if s:
            out.add(s)
    return out


def collect() -> list[str]:
    found: set[str] = set()
    if SOURCE_FILE.exists():
        found |= extract(SOURCE_FILE.read_text(encoding="utf-8"))
    root = HERE.parent.parent.parent  # workspace root
    for pat in ("ROW_*.md", "ERG_*.md"):
        for f in root.glob(pat):
            try:
                found |= extract(f.read_text(encoding="utf-8"))
            except OSError:
                pass
    found |= set(WEATHER) | set(REVIEW_MARKERS)
    return sorted(found, key=lambda s: [ord(c) for c in s])


def main() -> int:
    check_only = "--check" in sys.argv
    emojis = collect()
    print(f"emoji 总数: {len(emojis)}")

    if check_only:
        cached = {p.stem for p in emoji_source.CACHE_DIR.glob("*.png")} if emoji_source.CACHE_DIR.exists() else set()
        missing = [e for e in emojis if not (set(emoji_source._candidates(e)) & cached)]
        print(f"已缓存文件: {len(cached)}   未覆盖: {len(missing)}")
        for e in missing:
            print("   MISSING", repr(e), emoji_source._candidates(e))
        return 0 if not missing else 1

    ok, fail = [], []
    for i, e in enumerate(emojis, 1):
        data = emoji_source._fetch_jsdelivr(e)
        (ok if data else fail).append(e)
        if i % 10 == 0:
            print(f"  ... {i}/{len(emojis)}", flush=True)

    size = sum(p.stat().st_size for p in emoji_source.CACHE_DIR.glob("*.png"))
    count = len(list(emoji_source.CACHE_DIR.glob("*.png")))
    print(f"\n成功 {len(ok)} / 失败 {len(fail)}")
    if fail:
        for e in fail:
            print("  FAIL", repr(e), emoji_source._candidates(e))
    print(f"缓存目录: {emoji_source.CACHE_DIR}")
    print(f"缓存大小: {size/1024:.1f} KB / {count} 个文件")
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
