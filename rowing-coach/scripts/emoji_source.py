"""Emoji rendering source that does not depend on emojicdn.elk.sh.

pilmoji's default Twemoji source builds URLs as ``https://emojicdn.elk.sh/<emoji>``.
That host has become unreliable (SSL EOF / timeouts), which made every image
render fail even though the charts themselves were fine.

This module keeps the same Twemoji artwork but resolves it from jsDelivr by
codepoint, with a small on-disk cache so repeat runs need no network at all.
The original source is still tried last, so behaviour degrades to the previous
code path if jsDelivr is also unavailable.
"""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Optional

CACHE_DIR = Path(__file__).resolve().parent.parent / ".emoji-cache"
JSDELIVR = "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/{name}.png"

_installed = False


def _candidates(emoji: str) -> list[str]:
    """Twemoji filename candidates, most likely first."""
    cps = [f"{ord(ch):x}" for ch in emoji]
    out = []
    # twemoji usually drops the FE0F variation selector
    no_fe0f = [c for c in cps if c != "fe0f"]
    if no_fe0f:
        out.append("-".join(no_fe0f))
    out.append("-".join(cps))
    # keep order stable while removing duplicates
    seen = set()
    return [c for c in out if not (c in seen or seen.add(c))]


def _fetch_jsdelivr(emoji: str) -> Optional[bytes]:
    import urllib.request

    for name in _candidates(emoji):
        cached = CACHE_DIR / f"{name}.png"
        if cached.exists() and cached.stat().st_size > 0:
            return cached.read_bytes()
        try:
            with urllib.request.urlopen(JSDELIVR.format(name=name), timeout=15) as r:
                data = r.read()
            if data:
                try:
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    cached.write_bytes(data)
                except OSError:
                    pass
                return data
        except Exception:
            continue
    return None


def install() -> None:
    """Patch pilmoji's CDN source to prefer jsDelivr (idempotent)."""
    global _installed
    if _installed:
        return
    try:
        from pilmoji import source as emoji_source
    except Exception:
        return

    original = emoji_source.EmojiCDNSource.get_emoji

    def get_emoji(self, emoji: str, /) -> Optional[io.BytesIO]:
        data = _fetch_jsdelivr(emoji)
        if data:
            return io.BytesIO(data)
        try:
            return original(self, emoji)
        except Exception:
            return None

    emoji_source.EmojiCDNSource.get_emoji = get_emoji
    _installed = True
