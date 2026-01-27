# Rowing Coach Skill 🚣‍♀️

Professional rowing coach assistant that analyzes FIT files and generates detailed training reports.

## Features

- **Multi-Source Support**: Compatible with FIT files from SpdCoach (on-water), Garmin, and Concept2 (indoor ERG).
- **Strategy C (Smart Segmentation)**: Uses 5-point smoothing and Change Point Detection (CPD) to accurately split training sessions into meaningful segments.
- **Deep Technical Analysis**:
    - **DPS (Distance Per Stroke)**: Evaluates technical efficiency against professional benchmarks.
    - **Pacing Strategy**: Identifies patterns like "Negative Splits" and power consistency.
    - **Zone Classification**: Automatically classifies training intensity (UT2, UT1, AT, TR, AN) based on Heart Rate Reserve (HRR) and stroke rate.
- **Coach Review**: Generates professional, actionable insights and technical recommendations in Chinese.
- **Visualization**: Automatically generates Pace & Cadence charts for visual review.

## Project Structure

```text
rowing-coach/
├── SKILL.md                # Skill definition for LLM
├── README.md               # This file
├── scripts/
│   └── parse_fit.py        # Core FIT parsing and analysis logic
├── references/
│   ├── coach_guidelines.md # Professional rowing coaching criteria
│   └── training_log_style.md # Markdown report template and style
└── .venv/                  # Python virtual environment (optional)
```

## Quick Start

### Installation

Requires Python 3.8+ and the following libraries:
- `fitparse`
- `matplotlib`
- `pandas`
- `geopy` (optional, for location data)

```bash
pip install fitparse matplotlib pandas geopy
```

## Usage in Antigravity Assistant

This skill is designed to work seamlessly with the **Antigravity** agentic assistant. It leverages task management and professional coaching guidelines to provide a comprehensive training review.

### Automatic 5-Step Workflow
Simply drag and drop your `.fit` file into the Antigravity chat and ask for an analysis:

> **User**: "分析一下这个赛艇 FIT 文件。"

Antigravity will automatically:
1. **Parse FIT file** → Extract data and generate `ANALYSIS_*.json`
2. **Generate coach review** → Read JSON and apply `coach_guidelines.md` criteria
3. **Update report** → Replace placeholder with professional Chinese feedback
4. **Regenerate share image** → Create `*_SHARE.png` with embedded review
5. **Cleanup** → Delete temporary JSON file

### Output Files
- `ROW_*.md` or `ERG_*.md` - Complete training report with coach review
- `*_SHARE.png` - Social media share image

## Technical CLI Usage (Advanced)
For developers or offline processing:

```bash
# Basic analysis
python3 scripts/parse_fit.py "path/to/session.fit"

# Analysis with custom HR settings
python3 scripts/parse_fit.py "session.fit" --max-hr 195 --resting-hr 60
```

## Example Analysis (Jan 24th Session)

### Input
File: `SpdCoach 2763073 20260124 0133PM.fit`

### Analysis Results (Full Segments)
| # | Time | Distance | Pace/500m | SPM | HR | DPS | Note |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 13:35 | 2300m | 2:57.2 | 19 | 118 | 8.9m | UT2 |
| 2 | 21:28 | 4000m | 2:41.0 | 18 | 140 | 10.4m | UT2 |
| 3 | 21:04 | 4000m | 2:38.0 | 18 | 142 | 10.5m | UT2 |
| 4 | 2:54 | 500m | 2:54.0 | 19 | 132 | 9.1m | UT2 |
| 5 | 3:18 | 500m | 3:18.0 | 19 | 124 | 8.0m | UT2 |
| 6 | 5:11 | 1000m | 2:35.8 | 18 | 135 | 10.7m | UT2 |

### Coach Review (AI Generated)

#### 🎯 训练总结
本次完成 **12.3km** 水上结构化训练，总用时 **68分钟**。亮点：**2x4km主训练段**，配速分别为 **2:41.0** 和 **2:38.0**，展现出负配速能力。心率从140升至142bpm，控制得当。

#### 💪 亮点
- **负配速执行出色**：第二个4k比第一个快3秒/500m，技术耐力提升明显
- **DPS持续提升**：从热身段8.9m → 主训练10.4m → 10.5m → 冲刺段10.7m
- **最佳500m 2:25.2/500m**，最佳1k **2:31.0/500m**

#### � 改进空间
- **Segment 5配速回落至3:18**（500m段），DPS降至8.0m，注意保持节奏
- **热身段偏长**：13分35秒热身可压缩至10分钟

#### 💡 下次训练建议
> 可尝试"3x3km"结构，目标配速递进(2:45→2:40→2:35)，保持DPS>10m。

### Share Image
The skill also generates a social media share image with all metrics and coach review embedded:

![Share Image Example](assets/example_share.png)

## License
MIT
