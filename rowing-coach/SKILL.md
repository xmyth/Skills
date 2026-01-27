---
name: rowing-coach
description: Professional rowing coach assistant that analyzes FIT files and generates detailed training reports. Use when the user uploads a .fit file from a rowing session (Concept2, Garmin, etc.) or asks for a rowing workout analysis.
---

# Rowing Coach

## Overview
This skill provides **automatic** professional analysis of rowing workouts. When invoked, it parses FIT files, generates a professional coach review, and produces a complete training report.

## Automatic Workflow

When analyzing a FIT file, execute **ALL** steps automatically without waiting for user input:

### Step 1: Parse FIT File
```bash
.gemini/skills/rowing-coach/.venv/bin/python3 .gemini/skills/rowing-coach/scripts/parse_fit.py <path_to_fit_file>
```
**Outputs**:
- `ROW_*.json` / `ERG_*.json` - Structured data for analysis
- `ROW_<timestamp>.md` or `ERG_<timestamp>.md` - Initial report with placeholder review
- `*_SHARE.png` - Social media image

### Step 2: Generate Professional Coach Review
**IMMEDIATELY** after Step 1:
1. Read the generated JSON analysis file (`*.json`)
2. Use `references/coach_guidelines.md` for analysis criteria and coaching style
3. Generate a professional, data-driven review in Chinese following the structure:
   - **训练总结**: Distance, time, training type
   - **亮点**: Specific strengths with data references
   - **改进空间**: Technical gaps with segment references
   - **下次训练建议**: Actionable drill or focus

### Step 3: Update Report
Replace the placeholder review in the generated `.md` file with your professional analysis.

### Step 4: Regenerate Share Image
```bash
.gemini/skills/rowing-coach/.venv/bin/python3 .gemini/skills/rowing-coach/scripts/parse_fit.py --regen-share <path_to_updated_md>
```
This regenerates the `*_SHARE.png` with the new coach review embedded.

### Step 5: Cleanup
Delete the temporary JSON analysis file after successful completion.

> **IMPORTANT**: All five steps must be completed automatically in a single invocation.

## Resources

### Scripts
- `.gemini/skills/rowing-coach/scripts/parse_fit.py`: Parses FIT files and generates initial reports.

### References
- `references/coach_guidelines.md`: Technical evaluation criteria (DPS benchmarks, zones, pacing).
- `references/training_log_style.md`: Report style guide.

## Example User Requests
- "Analyze this rowing session."
- "Generate a training report for this file."
- "How was my pacing on this 5k?"
