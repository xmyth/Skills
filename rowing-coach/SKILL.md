---
name: rowing-coach
description: Professional rowing coach assistant that analyzes FIT files and generates detailed training reports. Use when the user uploads a .fit file from a rowing session (Concept2, Garmin, SpeedCoach, etc.) or asks for a rowing workout analysis.
---

# Rowing Coach

## Overview
This skill provides **automatic** professional analysis of rowing workouts. When invoked, it parses FIT files, generates a professional coach review, and produces a complete training report.

## Automatic Workflow

When analyzing a FIT file, execute **ALL** steps automatically without waiting for user input:

### Step 1: Parse FIT File
```bash
python3 scripts/parse_fit.py <path_to_fit_file>
```
> The skill directory is the working directory. Adjust the Python path (`python3`, `.venv/bin/python3`) to match your environment.

**Outputs**:
- `ROW_*.json` / `ERG_*.json` - Structured data for analysis
- `ROW_<timestamp>.md` or `ERG_<timestamp>.md` - Initial report with placeholder review
- `*_SHARE.png` - Social media image

### Step 2: Generate Professional Coach Review
**IMMEDIATELY** after Step 1:
1. Read the generated JSON analysis file (`*.json`)
2. Use `references/coach_guidelines.md` for analysis criteria and coaching style
3. Generate a professional, data-driven review in English following the structure:
   - **Training Summary**: Distance, time, training type
   - **Highlights**: Specific strengths with data references
   - **Improvements**: Technical gaps with segment references
   - **Next Session Advice**: Actionable drill or focus

### Step 3: Update Report
Replace the placeholder review in the generated `.md` file with your professional analysis.

### Step 4: Regenerate Share Image
```bash
python3 scripts/parse_fit.py --regen-share <path_to_updated_md>
```
This regenerates the `*_SHARE.png` with the new coach review embedded.

### Step 5: Generate Xiaohongshu Post
**IMMEDIATELY** after Step 4:
1. Read the fully updated `.md` report (now including the professional coach review).
2. Generate a social media post suitable for Xiaohongshu (Red Note) in Chinese.
3. The post should include:
    - **Catchy Title**: Use emojis and an engaging hook.
    - **Key Stats**: Distance, Total Time, Average Pace, Stroke Rate.
    - **Coach's "One Thing"**: A single, impactful piece of advice or encouragement from the review.
    - **Tags**: Relevant hashtags (e.g., #赛艇 #Rowing #Concept2 #训练打卡).
4. Append this content to the end of the `.md` file under a new header `## Social Media Post`.

### Step 6: Cleanup
Delete the temporary JSON analysis file after successful completion.

> **IMPORTANT**: All six steps must be completed automatically in a single invocation.

## Adaptive Segmentation Algorithm

The `parse_fit.py` script uses a multi-layered adaptive segmentation approach:

1. **Device Laps**: If the FIT file contains native lap markers, they are used directly (gold standard).
2. **HR Valley** (with HR data): Finds HR local minima (> 6 bpm drop from prior peak), validates with pace slowdown and cadence collapse, then backtracks to find rest start and forward to find rest end.
3. **Speed Collapse** (no HR data): Finds speed drops below 35% of session median, validates surrounding data, and applies the same backtrack/forward logic.
4. **Gap Detection** (always active): Hardware data gaps > 3× median sampling interval (min 10s) with surrounding speed validation.

All thresholds are relative and adaptive — no hardcoded pace or HR values.

## Resources

### Scripts
- `scripts/parse_fit.py`: Core FIT parsing, adaptive segmentation, and report generation.

### References
- `references/coach_guidelines.md`: Technical evaluation criteria (DPS benchmarks, zones, pacing).
- `references/training_log_style.md`: Report style guide.

## Example User Requests
- "Analyze this rowing session."
- "Generate a training report for this file."
- "How was my pacing on this 5k?"
