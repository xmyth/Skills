---
name: nk-logbook-downloader
description: Downloads the latest workout FIT files from the NK Sports logbook (logbook.nksports.com) via the internal API. After downloading, automatically invokes the rowing-coach skill on each new file.
---

# NK Logbook Downloader

## Overview

Downloads new workout FIT files from the NK Sports logbook by calling its internal API directly. A JWT token is obtained once via browser login and persisted for subsequent runs. No credentials are stored — the JWT is saved locally in `.jwt`.

After download, each new FIT file is automatically analyzed by the rowing-coach skill.

## Workflow

### Step 1: Download new FIT files

```bash
python3 scripts/download.py ~/Devel/claude_code
```

The script:
1. Reads the saved JWT from `.jwt` (or launches a one-time browser login to obtain it)
2. Calls `logbook-api.nksports.com/api/stream/range` to list all sessions
3. Compares session `startTime` against existing `SpdCoach *.fit` files for dedup
4. Calls `logbook-api.nksports.com/api/stream/export/{id}/fit` for each new session
5. Base64-decodes the `resource` field and saves the FIT file

Output: Prints paths to newly downloaded FIT files, one per line.

### Step 2: Analyze each new file

For each downloaded FIT file, immediately invoke the rowing-coach skill to generate the full training report.

### One-time setup

On first run, if no `.jwt` exists, the script opens a Chromium browser for manual login to `logbook.nksports.com/login/sign-in`. After successful login, the JWT is extracted from localStorage and saved to `.jwt`. The JWT expires in 2031, so re-login is rare.

### Error cases

- **No .jwt and login fails:** Script exits with instructions
- **JWT expired:** Script clears `.jwt` and prompts re-login
- **API unreachable:** Script exits with error message
- **Single download fails:** Skipped and reported

### Known data problems

#### SpeedCoach memory full → recording truncated

When the unit's memory fills mid-session it stops writing samples, but still
writes a **complete session summary** at the end. The export therefore looks
self-contradictory: a full distance/duration in the summary, while the record
stream covers only the first part of the row.

Signature (2026-10-20 session):

| Field | Value |
| :--- | ---: |
| `session.total_distance` | 14161 m |
| `session.total_elapsed_time` | 4157 s |
| record stream span | 830 s |
| recorded distance | 2121 m (≈15% of the row) |
| `sum(laps.distance)` | 2022 m |

**How to detect** — compare the record span with the session elapsed time, or
`sum(laps.distance)` with `session.total_distance`. A large shortfall means
truncation, not a corrupt file: the FIT parses fine and the summary is genuine.

**How to handle**

- The missing part cannot be recovered from the export — do not treat the gap as
  a data error and do not rescale or interpolate it.
- Do not produce a normal report from a truncated session: the segment table
  would cover only the recorded fraction while the header quotes the full row.
- Mark the analysed JSON so later batch statistics skip it:

  ```json
  "truncated": true,
  "truncation": { "reason": "...", "records_span_s": 830,
                  "recorded_fraction": 0.15, ... }
  ```

  Any script that walks `ROW_*.json` should skip entries with `truncated: true`.
- Prevention: clear the SpeedCoach memory before races and long sessions.


## Example User Requests

- "Download my latest workouts"
- "Sync workouts from NK logbook"
- "Check for new rowing sessions"
- "Download and analyze new workouts"
