#!/usr/bin/env python3
"""Download new FIT files from NK Sports logbook via the internal API.

Calls the logbook API directly with a JWT token. On first run, opens a browser
for manual login and saves the JWT. Subsequent runs use the saved JWT.

API endpoints:
  POST /api/authenticate            — login, returns JWT
  GET  /api/stream/range/{start}-{end}  — list sessions
  GET  /api/stream/export/{id}/fit  — download FIT (base64 in JSON)
"""

import sys
import os
import re
import time
import json
import base64
from pathlib import Path

import requests

API_BASE = "https://logbook-api.nksports.com"
SKILL_DIR = Path(__file__).resolve().parent.parent
JWT_FILE = SKILL_DIR / ".jwt"
PROFILE_DIR = SKILL_DIR / "profile"

FIT_FILENAME_RE = re.compile(
    # Legacy exports carry a device serial ("SpdCoach 2763073 20250702 0755AM.fit");
    # current ones don't ("SpdCoach 20260708 0633AM.fit"). The serial is optional
    # so both formats dedup — otherwise every serial-less file re-downloads each run.
    r"^SpdCoach (?:\d+ )?(\d{8}) (\d{4})(AM|PM)\.fit$"
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_jwt() -> str | None:
    """Return a valid JWT, obtaining one via browser login if needed."""
    if JWT_FILE.exists():
        jwt = JWT_FILE.read_text().strip()
        if jwt:
            return jwt
    return login_and_save_jwt()


def login_and_save_jwt() -> str | None:
    """Launch visible Chromium for manual login, extract and persist the JWT."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright not installed. Run: pip install playwright && "
            "playwright install chromium",
            file=sys.stderr,
        )
        return None

    print("Opening browser for NK Sports login…")
    print("Log in with your credentials. The browser will close automatically.")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=False
        )
        page = ctx.new_page()
        page.goto(
            "https://logbook.nksports.com/login/sign-in",
            wait_until="domcontentloaded",
            timeout=30000,
        )

        try:
            page.wait_for_url(
                "https://logbook.nksports.com/", timeout=300000
            )
        except Exception:
            print("Login timed out.", file=sys.stderr)
            ctx.close()
            return None

        page.wait_for_timeout(2000)

        jwt = page.evaluate(
            "() => { for (let i = 0; i < localStorage.length; i++) {"
            "  const v = localStorage.getItem(localStorage.key(i));"
            "  if (v && v.startsWith('eyJ')) return v;"
            "} return ''; }"
        )

        ctx.close()

        if not jwt:
            print(
                "Could not find JWT in localStorage. The site may have changed.",
                file=sys.stderr,
            )
            return None

        JWT_FILE.write_text(jwt)
        print("Login successful. JWT saved.")
        return jwt


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def list_sessions(jwt: str) -> list[dict]:
    """Fetch all workout sessions."""
    end_ms = int(time.time() * 1000) + 86_400_000
    url = f"{API_BASE}/api/stream/range/1-{end_ms}"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {jwt}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_export_metadata(jwt: str, stream_id: int) -> dict | None:
    """Fetch export metadata (filename + base64 data) for one session."""
    url = f"{API_BASE}/api/stream/export/{stream_id}/fit"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {jwt}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data[0] if data else None


# ---------------------------------------------------------------------------
# Dedup helpers
# ---------------------------------------------------------------------------

def parse_existing_timestamps(output_dir: Path) -> set[str]:
    """Return YYYYMMDDHHMM keys of existing SpdCoach FIT files."""
    keys: set[str] = set()
    for f in output_dir.iterdir():
        m = FIT_FILENAME_RE.match(f.name)
        if m:
            date_str, time_str, ampm = m.group(1), m.group(2), m.group(3)
            hour = int(time_str[:2])
            minute = int(time_str[2:])
            if ampm == "PM" and hour != 12:
                hour += 12
            elif ampm == "AM" and hour == 12:
                hour = 0
            keys.add(f"{date_str}{hour:02d}{minute:02d}")
    return keys



# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def start_time_to_key(start_time_ms: int) -> str:
    """Convert epoch ms to YYYYMMDDHHMM string (UTC, matches FIT filename)."""
    from datetime import datetime, timezone
    dt = datetime.fromtimestamp(start_time_ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y%m%d%H%M")


def main():
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    if not output_dir.is_dir():
        print(f"Not a directory: {output_dir}", file=sys.stderr)
        sys.exit(1)

    jwt = get_jwt()
    if not jwt:
        print("Failed to obtain JWT. Cannot continue.", file=sys.stderr)
        sys.exit(1)

    existing_keys = parse_existing_timestamps(output_dir)

    print("Fetching session list…")
    try:
        sessions = list_sessions(jwt)
    except requests.RequestException as e:
        print(f"Failed to fetch sessions: {e}", file=sys.stderr)
        if JWT_FILE.exists():
            JWT_FILE.unlink()
        sys.exit(1)

    print(f"Found {len(sessions)} total sessions.")

    # Dedup using startTime to identify new sessions without calling export API
    new_sessions: list[dict] = []
    for s in sessions:
        stream_id = s.get("totalStreamId")
        start_time = s.get("startTime")
        if not stream_id or not start_time:
            continue
        time_key = start_time_to_key(start_time)
        if time_key not in existing_keys:
            new_sessions.append(s)

    print(f"{len(new_sessions)} new session(s) to download.")

    if not new_sessions:
        print("No new workouts found.")
        return

    new_downloads: list[str] = []

    for session in new_sessions:
        stream_id = session["totalStreamId"]
        boat_name = session.get("boatName", "Unknown")

        try:
            entry = get_export_metadata(jwt, stream_id)
        except requests.RequestException as e:
            print(f"SKIP: {boat_name} — API error: {e}", file=sys.stderr)
            continue

        if not entry:
            print(f"SKIP: {boat_name} — empty response", file=sys.stderr)
            continue

        filename = entry.get("name", "")
        if not filename or not filename.endswith(".fit"):
            print(f"SKIP: {boat_name} — unexpected filename: {filename}", file=sys.stderr)
            continue

        resource = entry.get("resource", "")
        if not resource:
            print(f"SKIP: {filename} — no data", file=sys.stderr)
            continue

        try:
            fit_data = base64.b64decode(resource)
        except base64.binascii.Error as e:
            print(f"SKIP: {filename} — base64 error: {e}", file=sys.stderr)
            continue

        dest = output_dir / filename
        dest.write_bytes(fit_data)
        print(str(dest))
        new_downloads.append(str(dest))

    if new_downloads:
        print(f"\nDownloaded {len(new_downloads)} new workout(s).")
    else:
        print("No new workouts found.")


if __name__ == "__main__":
    main()
