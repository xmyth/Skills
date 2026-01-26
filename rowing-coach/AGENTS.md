# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Repository Overview

This is a **Rowing Coach Skill** for LLM assistants that analyzes FIT files from rowing sessions and generates professional training reports in Chinese. It supports multi-source FIT files (SpdCoach on-water, Garmin, Concept2 ERG) and uses Change Point Detection (CPD) to intelligently segment workouts.

### Core Workflow
1. **Parse FIT file** → Extract metrics using `scripts/parse_fit.py`
2. **LLM Analysis** → Read generated JSON and act as professional rowing coach
3. **Generate Report** → Create detailed Markdown training log with technical feedback

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Parser
```bash
# Basic usage (use venv Python to ensure dependencies are available)
.venv/bin/python3 scripts/parse_fit.py <path_to_fit_file>

# With custom HR settings for accurate zone classification
.venv/bin/python3 scripts/parse_fit.py <path_to_fit_file> --max-hr 195 --resting-hr 60

# Direct execution (script has shebang)
./scripts/parse_fit.py <path_to_fit_file>
```

The parser outputs:
- `ANALYSIS_<timestamp>.json` - Structured data for LLM coach review
- `ROW_<timestamp>.md` - Initial Markdown report with placeholder for coach analysis
- `PACE_CADENCE_<timestamp>.png` - Visual pacing chart

### Testing
There are no automated tests in this repository. Validation is done by:
1. Running parse script on sample FIT files
2. Manually reviewing generated JSON structure and Markdown reports
3. Verifying chart visualization accuracy

## Architecture & Key Concepts

### Three-Stage Processing Pipeline

#### Stage 1: FIT Parsing (`parse_fit.py`)
Extracts raw data from FIT files using the `fitparse` library:
- **Session-level metrics**: Total distance, time, calories, HR zones
- **Record-level data**: Time-series of speed, cadence, HR, power (typically 1Hz sampling)
- **Lap data**: Pre-defined intervals (if device recorded them)

#### Stage 2: Smart Segmentation (Strategy C)
When lap data is sparse or missing, the script uses **Change Point Detection**:

**Preprocessing**:
- Outlier removal (SPM > 60)
- 10-point moving average smoothing on speed and cadence

**Segmentation Logic** (`auto_segment()`):
- Monitors local speed trend vs. segment mean
- Triggers split when divergence exceeds 0.6 m/s AND segment duration > 45s
- Special case: Rest detection (speed < 1.0 m/s) allows earlier split at 20s
- Filters segments < 100m as noise

This avoids over-segmentation while capturing meaningful training blocks.

#### Stage 3: LLM Coach Analysis
The LLM reads `ANALYSIS_*.json` and acts as a professional rowing coach using:
- `references/coach_guidelines.md` - Technical evaluation criteria (DPS benchmarks, pacing strategy)
- `references/training_log_style.md` - Report structure and Chinese coaching tone

**Key Metrics**:
- **DPS (Distance Per Stroke)**: Primary technical efficiency indicator
  - \>10.5m = Excellent, 8.5-10.5m = Good, <8.5m = Needs improvement
- **Training Zones**: Classified by HRR% (Heart Rate Reserve)
  - UT2 (<65%), UT1 (65-75%), AT (75-85%), TR (85-95%), AN (>95%)
- **Pacing Consistency**: Standard deviation of splits across segments

### Indoor vs. On-Water Differentiation

**Indoor (Concept2 ERG)**:
- Uses FIT `intensity` field to detect Work/Rest intervals
- Automatic workout phase detection: Warm-up → Main Sets → Cool-down
- Phase transitions marked by first/last rest intervals

**On-Water (SpdCoach, Garmin)**:
- Relies on CPD segmentation for natural training block boundaries
- Optional geopy integration for location name reverse geocoding
- No phase detection (just Work/Rest classification)

### Data Flow
```
FIT File → parse_fit.py → ANALYSIS_*.json
                        → ROW_*.md (with placeholder)
                        → PACE_CADENCE_*.png

ANALYSIS_*.json → [LLM reads] → Professional Chinese analysis → Update ROW_*.md
```

## Key Files

- `scripts/parse_fit.py` (1271 lines) - Core parsing, segmentation, analysis, visualization
- `references/coach_guidelines.md` - Rowing coaching evaluation criteria and benchmarks
- `references/training_log_style.md` - Markdown report template and Chinese style guide
- `SKILL.md` - LLM skill definition (workflow instructions for assistant)
- `requirements.txt` - Python dependencies

## Important Context for Code Changes

### HR Configuration
Lines 40-45 in `parse_fit.py` define global HR thresholds:
```python
MAX_HR = 195      # Maximum heart rate
RESTING_HR = 60   # Resting heart rate
```
These can be overridden via CLI args (`--max-hr`, `--resting-hr`). HRR% is used for accurate training zone classification rather than simple %MaxHR.

### Segmentation Tuning
If auto-segmentation is too aggressive or too coarse:
- Line 503: `CHANGE_THRESH = 0.4` (currently unused, kept for reference)
- Line 530: Main threshold `diff > 0.6` controls split sensitivity
- Lines 531-534: Duration gates (45s for normal, 20s for rest detection)

### Chart Generation
Requires `matplotlib` and `pandas`. Function `generate_pacing_chart()` starts at line 756. Uses smoothed data from Strategy C preprocessing for cleaner visualization.

## When Working with This Codebase

1. **Analyzing FIT files**: Always use the venv Python interpreter to ensure dependencies
2. **Modifying segmentation**: Test changes with both steady-state (single long lap) and interval workouts
3. **LLM coach review**: Must read `references/coach_guidelines.md` to provide technically accurate feedback. Focus on DPS, pacing strategy, and zone-appropriate training stimulus.
4. **Report generation**: Follow `references/training_log_style.md` for consistent Chinese coaching tone (professional, data-driven, encouraging)
5. **Location data**: Geopy is optional - script gracefully handles missing location information
