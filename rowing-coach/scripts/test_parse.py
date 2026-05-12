#!/usr/bin/env python3
"""Minimal test suite for rowing-coach parse_fit.py. Run from the skill root.

Usage:
    python3 scripts/test_parse.py
"""

import json
import os
import re
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARSE_SCRIPT = os.path.join(SKILL_DIR, "scripts", "parse_fit.py")
FIXTURES_DIR = os.path.join(SKILL_DIR, "test_fixtures")

# ---- Test definitions --------------------------------------------------------

TESTS = {
    "erg_steady.fit": {
        "desc": "Indoor steady-state ERG, no rests",
        "min_segments": 3,
        "max_segments": 8,
        "expect_rest": False,
        "pace_range": (130, 145),
        "spm_range": (15, 22),
        "hr_range": (120, 160),
        "dps_range": (9, 14),
        "time_tolerance": 0.5,
    },
    "erg_intervals.fit": {
        "desc": "Indoor intervals, 28 segments, AT/TR zones",
        "min_segments": 20,
        "max_segments": 35,
        "expect_rest": False,
        "pace_range": (125, 160),
        "spm_range": (14, 32),
        "hr_range": (130, 185),
        "dps_range": (6, 14),
        "time_tolerance": 0.5,
    },
    "row_no_hr.fit": {
        "desc": "On-water, no HR, Speed Collapse fallback",
        "min_segments": 2,
        "max_segments": 5,
        "expect_rest": True,
        "pace_range": (160, 250),
        "spm_range": (10, 25),
        "hr_range": (0, 10),
        "dps_range": (7, 14),
        "time_tolerance": 1.0,
    },
    "row_hr.fit": {
        "desc": "On-water, HR Valley segmentation",
        "min_segments": 5,
        "max_segments": 10,
        "expect_rest": True,
        "pace_range": (160, 250),
        "spm_range": (12, 25),
        "hr_range": (100, 180),
        "dps_range": (5, 14),
        "time_tolerance": 1.0,
    },
}

# ---- Helpers -----------------------------------------------------------------

def green(s):  return f"\033[32m{s}\033[0m"
def red(s):    return f"\033[31m{s}\033[0m"

def parse_output_paths(stdout):
    """Parse file paths from parse_fit.py stdout."""
    paths = {}
    for line in stdout.splitlines():
        m = re.search(r'(?:JSON generated|Chart image saved|Markdown|XHS Image):\s+(.+)', line)
        if m:
            path = m.group(1).strip()
            if path.endswith('.json'):
                paths['json'] = path
            elif path.endswith('.md'):
                paths['md'] = path
            elif path.endswith('_XHS.png'):
                paths['xhs'] = path
            elif path.endswith('.png'):
                paths['png'] = path
    # Check for SHARE.png
    for line in stdout.splitlines():
        m = re.search(r'Share image.*?:\s*(.+)', line)
        if m:
            paths['share'] = m.group(1).strip()
    return paths


def run_fixture(fixture_name, spec):
    """Run parse_fit.py on a fixture and return (errors, warnings)."""
    fit_path = os.path.join(FIXTURES_DIR, fixture_name)
    if not os.path.exists(fit_path):
        return [f"Fixture not found: {fit_path}"], []

    # Run parse_fit.py
    result = subprocess.run(
        [sys.executable, PARSE_SCRIPT, fit_path],
        capture_output=True, text=True, timeout=30,
        cwd=FIXTURES_DIR,
    )
    stdout = result.stdout + result.stderr

    if result.returncode != 0:
        return [f"Exit code {result.returncode}", stdout[-400:]], []

    paths = parse_output_paths(stdout)
    errors = []
    warnings = []

    # 1. Output files exist
    if 'json' not in paths:
        errors.append("JSON output not found in stdout")
    if 'md' not in paths:
        errors.append("MD output not found in stdout")
    if 'png' not in paths:
        errors.append("PNG output not found in stdout")
    if 'share' in paths:
        errors.append(f"SHARE.png should not be generated: {paths['share']}")
    if 'xhs' not in paths:
        errors.append("XHS image not generated (missing 📱 XHS Image in stdout)")
    elif not os.path.exists(paths['xhs']):
        errors.append(f"XHS file does not exist: {paths['xhs']}")

    for key in ('json', 'md', 'png'):
        if key in paths and not os.path.exists(paths[key]):
            errors.append(f"{key.upper()} file does not exist: {paths[key]}")

    if errors:
        return errors, warnings

    # 2. JSON structure
    with open(paths['json']) as f:
        data = json.load(f)

    for key in ("session_info", "aggregated_metrics", "segments"):
        if key not in data:
            errors.append(f"Missing JSON key: {key}")
    if errors:
        return errors, warnings

    # 3. Metrics sanity
    am = data.get("aggregated_metrics", {})
    metrics = {
        "Pace": (am.get("avg_pace_per_500m", 0), spec["pace_range"]),
        "SPM":  (am.get("avg_cadence", 0), spec["spm_range"]),
        "HR":   (am.get("avg_heart_rate", 0), spec["hr_range"]),
        "DPS":  (am.get("avg_dps", 0), spec["dps_range"]),
    }
    for name, (value, (lo, hi)) in metrics.items():
        if not (lo <= value <= hi):
            errors.append(f"{name} {value} outside [{lo}, {hi}]")

    # 4. Time consistency
    si = data.get("session_info", {})
    segs = data.get("segments", [])
    reported = si.get("total_time_min", 0)
    seg_sum = sum(s.get("time_sec", 0) for s in segs) / 60
    diff = abs(reported - seg_sum)
    tol = spec["time_tolerance"]
    if diff > tol and not (reported > seg_sum and diff < 3):
        errors.append(
            f"total_time_min={reported:.1f} != seg_sum={seg_sum:.1f} (diff={diff:.1f})"
        )
    elif diff > 0.1:
        warnings.append(f"total_time_min={reported:.1f} vs seg_sum={seg_sum:.1f} (diff={diff:.1f}, OK)")

    # 5. Segment count
    n_segs = len(segs)
    lo, hi = spec["min_segments"], spec["max_segments"]
    if not (lo <= n_segs <= hi):
        errors.append(f"Segment count {n_segs} outside [{lo}, {hi}]")

    # 6. Work/Rest classification
    if spec["expect_rest"]:
        work_segs = [s for s in segs if s.get("type") == "Work"]
        rest_segs = [s for s in segs if s.get("type") == "Rest"]
        if not rest_segs:
            errors.append("Expected Rest segments but none found")
        elif not work_segs:
            errors.append("Expected Work segments but none found")

    # 7. Cleanup generated files
    for key in ('json', 'md', 'png', 'xhs'):
        if key in paths and os.path.exists(paths[key]):
            os.remove(paths[key])

    return errors, warnings


# ---- Main --------------------------------------------------------------------

def main():
    print("Rowing Coach Test Suite\n")
    total = 0
    passed = 0

    for fixture_name, spec in TESTS.items():
        total += 1
        print(f"  {fixture_name} ({spec['desc']})")

        errors, warnings = run_fixture(fixture_name, spec)
        if errors:
            print(f"    {red('FAIL')}")
            for e in errors:
                print(f"      {red('✗')} {e}")
        else:
            passed += 1
            print(f"    {green('PASS')}")
            for w in warnings:
                print(f"      ⚠ {w}")

    summary = f"{passed}/{total} passed"
    print(f"\n  {green(summary)}" if passed == total else f"\n  {red(summary)}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
