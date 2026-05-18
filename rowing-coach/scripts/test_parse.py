#!/usr/bin/env python3
"""Minimal test suite for rowing-coach parse_fit.py. Run from the skill root."""

import json
import os
import re
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARSE_SCRIPT = os.path.join(SKILL_DIR, "scripts", "parse_fit.py")
FIXTURES_DIR = os.path.join(SKILL_DIR, "test_fixtures")

TESTS = {
    "erg_steady.fit": {"desc": "Indoor steady-state ERG, no rests", "min_segs": 3, "max_segs": 8},
    "erg_intervals.fit": {"desc": "Indoor intervals, 28 segments, AT/TR zones", "min_segs": 20, "max_segs": 35},
    "row_no_hr.fit": {"desc": "On-water, no HR, Speed Collapse fallback", "min_segs": 2, "max_segs": 5},
    "row_hr.fit": {"desc": "On-water, HR Valley segmentation", "min_segs": 5, "max_segs": 10},
}

MOCK_REVIEW = "### Highlights\n- Good pacing.\n### Improvements\n- Keep length.\n### Next Session\n- 3x2km."
MOCK_XHS = "test"

def green(s): return f"\033[32m{s}\033[0m"
def red(s): return f"\033[31m{s}\033[0m"

def run_fixture(fixture_name, spec):
    fit_path = os.path.join(FIXTURES_DIR, fixture_name)
    if not os.path.exists(fit_path):
        return [f"Fixture not found: {fit_path}"], []

    # Step 1: Parse FIT → JSON only
    result = subprocess.run(
        [sys.executable, PARSE_SCRIPT, fit_path],
        capture_output=True, text=True, timeout=30, cwd=FIXTURES_DIR,
    )
    stdout1 = result.stdout + result.stderr
    if result.returncode != 0:
        return [f"JSON-only mode exit code {result.returncode}", stdout1[-400:]], []

    # Find JSON path
    json_path = None
    for line in stdout1.splitlines():
        m = re.search(r'JSON generated:\s+(.+)', line)
        if m:
            json_path = m.group(1).strip()
            break
    if not json_path or not os.path.exists(json_path):
        return ["JSON not generated in step 1"], []

    errors, warnings = [], []

    # Validate JSON
    with open(json_path) as f:
        data = json.load(f)
    for key in ("session_info", "aggregated_metrics", "segments"):
        if key not in data:
            errors.append(f"Missing JSON key: {key}")
    n = len(data.get("segments", []))
    if not (spec["min_segs"] <= n <= spec["max_segs"]):
        errors.append(f"Seg count {n} outside [{spec['min_segs']},{spec['max_segs']}]")
    # Time consistency
    si = data["session_info"]
    segs = data["segments"]
    reported = si.get("total_time_min", 0)
    seg_sum = sum(s.get("time_sec", 0) for s in segs) / 60
    diff = abs(reported - seg_sum)
    if diff > 1.5 and not (reported > seg_sum and diff < 5):
        errors.append(f"total_time_min={reported:.1f} != seg_sum={seg_sum:.1f}")
    elif diff > 0.1:
        warnings.append(f"time diff {diff:.1f} min (OK)")

    # Step 2: --build-report
    result2 = subprocess.run(
        [sys.executable, PARSE_SCRIPT, "--build-report", json_path,
         "--review", MOCK_REVIEW, "--xhs-post", MOCK_XHS],
        capture_output=True, text=True, timeout=30, cwd=FIXTURES_DIR,
    )
    stdout2 = result2.stdout + result2.stderr
    if result2.returncode != 0:
        errors.append(f"--build-report exit code {result2.returncode}")
        return errors, warnings

    # Check outputs
    for label, pattern in [("MD", "Markdown:"), ("Chart", "Chart Image:"),
                            ("XHS1", "XHS Page 1:"), ("XHS2", "XHS Page 2:")]:
        found = False
        for line in stdout2.splitlines():
            m = re.search(re.escape(pattern) + r'\s*(.+)', line)
            if m:
                p = m.group(1).strip()
                if os.path.exists(p):
                    os.remove(p)
                    found = True
                break
        if not found:
            errors.append(f"{label} not generated")

    # Cleanup JSON
    if os.path.exists(json_path):
        os.remove(json_path)

    return errors, warnings


def main():
    print("Rowing Coach Test Suite\n")
    total = passed = 0
    for name, spec in TESTS.items():
        total += 1
        print(f"  {name} ({spec['desc']})")
        errors, warnings = run_fixture(name, spec)
        if errors:
            print(f"    {red('FAIL')}")
            for e in errors: print(f"      {red('✗')} {e}")
        else:
            passed += 1
            print(f"    {green('PASS')}")
            for w in warnings: print(f"      ⚠ {w}")
    summary = f"{passed}/{total} passed"
    print(f"\n  {green(summary)}" if passed == total else f"\n  {red(summary)}")
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
