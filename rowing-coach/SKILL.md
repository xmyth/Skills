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
- `ROW_<timestamp>.png` or `ERG_<timestamp>.png` - Pacing chart image
- `ROW_<timestamp>_XHS.png` or `ERG_<timestamp>_XHS.png` - Xiaohongshu training image

### Step 2: Generate Coach Review + XHS Post + Build Report
**IMMEDIATELY** after Step 1:
1. Read the generated JSON analysis file (`*.json`)
2. Use `references/coach_guidelines.md` for analysis criteria and coaching style
3. Generate a professional, data-driven review in **Chinese** following the structure:
   - **Highlights** (🌟 亮点): Specific strengths with data references
   - **Improvements** (⚡ 改进): Technical gaps with segment references
   - **Next Session** (🎯 下次训练): Actionable drill or focus
4. Generate a Xiaohongshu social media post in Chinese using this format:
```
🚣 [日期] 水上训练 | [距离] [训练类型]

📊 今日数据
· 距离：[dist]km
· 用时：[time]min
· 配速：[pace]/500m
· 桨频：[spm]spm · 心率：[hr]bpm
· [weather emoji] [天气] [temp]°C · [城市]

📋 分段详情
🔥 [dist]m @ [pace] · [spm]spm · HR[hr]
💤 休息  ↓[min_hr]
... (one line per segment, 🔥 for hot zones AT/TR/AN, 💤 for rest)

💡 教练点评
[one impactful takeaway from the review]

#赛艇 #rowing #[tag]
```
5. Build all outputs:
```bash
python3 scripts/parse_fit.py --build-report <file.json> \
    --review "### Highlights\n- ...\n### Improvements\n- ...\n### Next Session\n- ..." \
    --xhs-post "..."
```

### Step 3: Cleanup
JSON preserved. No other temp artifacts.

> **IMPORTANT**: All three steps must be completed automatically in a single invocation.

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
