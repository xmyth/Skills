---
name: rowing-coach
description: Professional rowing coach assistant that analyzes FIT files and generates detailed training reports. Use when the user uploads a .fit file from a rowing session (Concept2, Garmin, etc.) or asks for a rowing workout analysis.
---

# Rowing Coach

## Overview
This skill provides professional analysis of rowing workouts using data from FIT files. It acts as a professional rowing coach to evaluate performance and generates engaging training logs.

## Workflow

1.  **Extract Data**:
    Run the `scripts/parse_fit.py` script. It will generate a partial Markdown report and a detailed `ANALYSIS_<timestamp>.json` file.
    ```bash
    .gemini/skills/rowing-coach/.venv/bin/python3 .gemini/skills/rowing-coach/scripts/parse_fit.py <path_to_fit_file>
    ```

2.  **LLM Coaching Analysis (Crucial)**:
    -   **Read Data**: Read the generated `.json` file from the previous step.
    -   **Analyze**: ACT AS A PROFESSIONAL ROWING COACH. Use the data and `references/coach_guidelines.md` to evaluate:
        -   **Technical Efficiency (DPS)**: Evaluate average Distance Per Stroke vs. benchmarks (8-12m).
        -   **Power Consistency**: Analyze pace consistency across segments.
        -   **Intensity & Pacing**: Review best efforts (2k, 4k) and segment types.
    -   **Generate Feedback**: Create professional, actionable, and encouraging insights in Chinese. Avoid generic advice; refer to specific segments and metrics from the data.

3.  **Generate Final Report**:
    Update the generated report or create a new one following `references/training_log_style.md`.
    -   **Replace Placeholder**: Replace the "等待 LLM 分析" placeholder with your professional analysis.
    -   **Content**: Focus on technical and physiological analysis.

4.  **Save/Update Final Report**:
    Ensure the final report with your expert analysis is saved in the same directory as the original FIT file.


## Resources

### Dependencies
- **fitparse**: Used to parse `.fit` files.
- **matplotlib**: Used to generate data-driven performance charts.
- **pandas**: Used for data manipulation and analysis.
- **geopy** (Local): Optional, used for reverse geocoding coordinates to location names.

### Scripts
- `.gemini/skills/rowing-coach/scripts/parse_fit.py`: Extracts session summary and record samples from FIT files. Returns JSON.

### References
- `.gemini/skills/rowing-coach/references/coach_guidelines.md`: Professional criteria for evaluating rowing technique and data.
- `.gemini/skills/rowing-coach/references/training_log_style.md`: Template and style guide for the output format.

## Example User Requests
- "Analyze this rowing session."
- "Generate a training report for this file."
- "How was my pacing on this 5k?"
