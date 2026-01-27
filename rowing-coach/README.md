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
1. **Parse FIT file** → Extract data and generate `ROW_*.json` or `ERG_*.json`
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

## Example Analysis (Jan 23rd On-Water Session)

### Input
File: `SpdCoach 2763073 20260123 0811AM.fit`

### Analysis Results (Full Segments)
| # | Time | Distance | Pace/500m | SPM | HR | DPS | Note |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 10:11 | 1479m | 3:26.4 | 18 | 104 | 8.1m | UT2 |
| 2 | 4:26 | 693m | 3:11.6 | 17 | 118 | 9.2m | UT2 |
| 3 | 24:39 | 4331m | 2:50.7 | 16 | 132 | 11.0m | UT2 |
| 4 | 18:14 | 3280m | 2:46.7 | 17 | 136 | 10.6m | UT2 |
| 5 | 8:39 | 1330m | 3:14.9 | 16 | 116 | 9.6m | UT2 |
| 6 | 1:03 | 110m | 4:43.8 | 19 | 101 | 5.6m | Rest |
| 7 | 5:07 | 913m | 2:48.1 | 17 | 122 | 10.5m | UT2 |
| 8 | 2:37 | 369m | 3:32.3 | 23 | 107 | 6.1m | UT2 |
| 9 | 0:55 | 154m | 2:58.2 | 15 | 117 | 11.2m | UT2 |

### Coach Review (AI Generated)

#### 🎯 训练总结
本次水上训练里程 **12.66km**，耗时 **75分钟**。
这是一堂典型的 **超低桨频技术耐力课 (Technical Endurance)**。
全程度保持在极低的桨频 (**16-18spm**)，心率控制在良好的有氧区间 (平均126bpm)，主要目的是在低强度下通过长距离划行寻找水感和船的滑行距离。

#### 🌟 亮点 (Highlights)
*   **耐心的节奏 (Patience)**: 在长距离段落（第3、4段）中，能够稳定维持在 16-17spm，没有盲目起桨频，这是练就好技术的心理基础。
*   **实效提升 (DPS Improvement)**: 热身阶段 DPS 仅 8.1m，但在进入主项后（第3段）提升至 **11.0m**，说明身体活动开了之后，推水实效有显著改善，每一桨都划得更“深”了。
*   **心率控制**: 绝大部分时间处于 UT2 甚至更低的有氧恢复区，非常适合作为大运动量后的恢复或纯技术课。

#### 🚀 改进空间 (Improvements)
*   **热身段实效不足**: 第1段和第2段的 DPS 都在 9m 以下。 建议即使是刚下水，也要专注于每一桨的“挂水”质量，不要“空划”。
*   **速度差异**: 第3段和第4段虽然桨频接近，但配速有一定波动（2:50 vs 2:46）。在自然水域可能受风浪影响，但我们要追求“顶风不掉速，顺风不抢频”。

#### 💡 下次训练建议
*   **起步即专注**: 尝试从下水的第一桨开始就关注 **包含 (Catch)** 和 **支撑 (Connection)**，争取热身时的 DPS 也能稳定在 10m 以上。
*   **力求恒定**: 在低桨频下，感受船体在拉桨结束后的滑行感（Run）。每一桨的力曲线尽量做饱满。

### Share Image
The skill also generates a social media share image with all metrics and coach review embedded:

![Share Image Example](assets/example_share.png)

## License
MIT
