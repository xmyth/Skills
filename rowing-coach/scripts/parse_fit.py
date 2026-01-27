#!/usr/bin/env python3
"""
FIT File Parser for Rowing Coach Skill

This script extracts key metrics from a FIT file suitable for rowing analysis.
It requires the 'fitparse' library.

Usage:
    python3 scripts/parse_fit.py <path_to_fit_file>
"""

import argparse
import sys
import json
import datetime
import os
import io

try:
    import fitparse
except ImportError:
    print("Error: 'fitparse' library is required. Please install it using: pip install fitparse")
    sys.exit(1)

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import pandas as pd
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# Optional geopy for location
try:
    from geopy.geocoders import Nominatim
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    from pilmoji import Pilmoji
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ============== HR CONFIGURATION ==============
# Configure these values for accurate HRR-based training zone classification
# HRR% = (Current HR - Resting HR) / (Max HR - Resting HR) * 100
MAX_HR = 195      # Maximum heart rate
RESTING_HR = 60   # Resting heart rate
# ==============================================

def calculate_hrr_percent(hr, max_hr=MAX_HR, resting_hr=RESTING_HR):
    """Calculate Heart Rate Reserve percentage."""
    if hr <= 0 or max_hr <= resting_hr:
        return 0
    hr_reserve = max_hr - resting_hr
    hrr_percent = ((hr - resting_hr) / hr_reserve) * 100
    return max(0, min(100, hrr_percent))  # Clamp to 0-100

def classify_training_zone(hr, spm=0, max_hr=MAX_HR, resting_hr=RESTING_HR):
    """
    Classify training zone based on HRR%, with SPM as secondary consideration.
    
    Training Zones (based on HRR%):
    - REST: Rest interval (detected from FIT file)
    - UT2: <65% HRR - Low aerobic / steady state
    - UT1: 65-75% HRR - Aerobic development
    - AT:  75-85% HRR - Anaerobic threshold
    - TR:  85-95% HRR - Transport / Race pace
    - AN:  >95% HRR - Anaerobic / Max effort
    """
    if hr <= 0:
        # Fallback to SPM-based classification if no HR data
        if spm <= 0:
            return ""
        elif spm <= 20:
            return "UT2"
        elif spm <= 24:
            return "UT1"
        elif spm <= 28:
            return "AT"
        else:
            return "TR"
    
    hrr = calculate_hrr_percent(hr, max_hr, resting_hr)
    
    if hrr < 65:
        return "UT2"
    elif hrr < 75:
        return "UT1"
    elif hrr < 85:
        return "AT"
    elif hrr < 95:
        return "TR"
    else:
        return "AN"

def get_location_name(lat_semicircles, lon_semicircles):
    """
    Reverse geocode semicircles to a City/Area name.
    """
    if not GEOPY_AVAILABLE:
        return None
        
    try:
        lat = semi_circles_to_degrees(lat_semicircles)
        lon = semi_circles_to_degrees(lon_semicircles)
        
        geolocator = Nominatim(user_agent="rowing_coach_skill_v1")
        # Zoom 10 is typically city level
        location = geolocator.reverse(f"{lat}, {lon}", zoom=10, language="en", timeout=10)
        
        if location:
            addr = location.raw.get("address", {})
            # Try to construct a compact name: City, District
            city = addr.get("city") or addr.get("county") or addr.get("state")
            district = addr.get("suburb") or addr.get("district")
            
            if city and district:
                return f"{city} · {district}"
            return city or location.address
            
    except Exception as e:
        print(f"DEBUG: Geopy Error: {e}", file=sys.stderr)
        return None
    
    return None

def semi_circles_to_degrees(semi_circles):
    if semi_circles is None:
        return None
    return semi_circles * (180.0 / 2**31)

def parse_fit(file_path):
    try:
        fitfile = fitparse.FitFile(file_path)
    except Exception as e:
        print(f"Error parsing FIT file: {e}")
        return None

    data = {
        "session": {},
        "records": [],
        "laps": []
    }

    # Parse Session
    for record in fitfile.get_messages("session"):
        session_data = {}
        for data_point in record:
            if data_point.name in [
                "total_timer_time", "total_distance", "total_calories", 
                "avg_speed", "max_speed", "avg_heart_rate", "max_heart_rate",
                "avg_cadence", "max_cadence", "total_strokes", "sport", "sub_sport",
                "start_time", "avg_power", "max_power", "total_ascent", "total_descent",
                "start_position_lat", "start_position_long"
            ]:
                value = data_point.value
                if isinstance(value, datetime.datetime):
                    value = value.isoformat()
                session_data[data_point.name] = value
        data["session"] = session_data

    # Parse Records (samples)
    records = []
    for record in fitfile.get_messages("record"):
        record_data = {}
        for data_point in record:
            if data_point.name in [
                "timestamp", "heart_rate", "cadence", "distance", "speed", "power",
                "position_lat", "position_long"
            ]:
                value = data_point.value
                if isinstance(value, datetime.datetime):
                    value = value.isoformat()
                record_data[data_point.name] = value
        if record_data:
            records.append(record_data)
            
    # Simple sampling to avoid huge JSONs output if needed, but we need full data for calc
    # We will keep full records in memory but maybe not print all of them if too large? 
    # For now, let's keep them all for accurate calculation.
    data["records"] = records

    # Parse Laps (Intervals)
    laps = []
    for record in fitfile.get_messages("lap"):
        lap_data = {}
        for data_point in record:
            if data_point.name in [
                "start_time", "total_elapsed_time", "total_timer_time", 
                "total_distance", "avg_speed", "max_speed", "avg_cadence", 
                "max_cadence", "avg_power", "max_power", "avg_heart_rate", 
                "max_heart_rate", "total_calories", "total_strokes", "intensity"
            ]:
                value = data_point.value
                if isinstance(value, datetime.datetime):
                    value = value.isoformat()
                lap_data[data_point.name] = value
        if lap_data:
            laps.append(lap_data)
            
    data["laps"] = laps

    return data

def calculate_split(speed_m_s):
    """Helper to convert speed (m/s) to 500m split string."""
    if not speed_m_s or speed_m_s <= 0:
        return "-"
    
    split_seconds = 500 / speed_m_s
    minutes = int(split_seconds // 60)
    seconds = int(split_seconds % 60)
    tenth = int((split_seconds - int(split_seconds)) * 10)
    return f"{minutes}:{seconds:02}.{tenth}"

def create_lap_from_records(records_chunk):
    """Summarize a list of records into a Lap object."""
    if not records_chunk: return {}
    
    r_start = records_chunk[0]
    r_end = records_chunk[-1]
    
    t_start = r_start["dt"]
    t_end = r_end["dt"]
    duration = (t_end - t_start).total_seconds()
    if duration == 0: duration = 1 # avoid div/0
    
    # Distance
    dist_start = r_start["dist"]
    dist_end = r_end["dist"]
    total_dist = dist_end - dist_start
    if total_dist < 0: total_dist = 0 # should not happen
    
    # Averages
    avg_spd = total_dist / duration
    
    # Cadence / HR / Power
    cadences = [float(r["data"].get("cadence",0)) for r in records_chunk if r["data"].get("cadence")]
    hrs = [float(r["data"].get("heart_rate",0)) for r in records_chunk if r["data"].get("heart_rate")]
    pwrs = [float(r["data"].get("power",0)) for r in records_chunk if r["data"].get("power")]
    
    avg_cad = sum(cadences)/len(cadences) if cadences else 0
    avg_hr = sum(hrs)/len(hrs) if hrs else 0
    avg_pwr = sum(pwrs)/len(pwrs) if pwrs else 0
    
    return {
        "start_time": t_start.isoformat(),
        "total_timer_time": duration,
        "total_elapsed_time": duration,
        "total_distance": total_dist,
        "avg_speed": avg_spd,
        "avg_cadence": int(avg_cad),
        "avg_heart_rate": int(avg_hr),
        "avg_power": int(avg_pwr)
    }

def find_best_effort(records, target_dist_m):
    """
    Find the fastest continuous segment of 'target_dist_m' using a sliding window.
    Returns: { "pace": "1:45.0", "time": "3:30", "start_time": ... }
    """
    if not records or len(records) < 2:
        return None
        
    best_pace_seconds = float('inf')
    best_effort = None
    
    start_idx = 0
    end_idx = 0
    n = len(records)
    
    while end_idx < n:
        # Check current window distance
        # We need cumulative distance from record objects if possible, or sum
        # The records have "distance" which is cumulative total distance.
        d_start = float(records[start_idx].get("distance", 0) or 0)
        d_end = float(records[end_idx].get("distance", 0) or 0)
        dist_diff = d_end - d_start
        
        if dist_diff >= target_dist_m:
            # Valid window found. Calculate pace.
            t_start_str = records[start_idx].get("timestamp")
            t_end_str = records[end_idx].get("timestamp")
            
            if t_start_str and t_end_str:
                t_start = datetime.datetime.fromisoformat(str(t_start_str))
                t_end = datetime.datetime.fromisoformat(str(t_end_str))
                duration = (t_end - t_start).total_seconds()
                
                if duration > 0:
                    # Calculate split (time per 500m)
                    # speed = dist / duration
                    # split = 500 / speed = 500 * duration / dist
                    split_seconds = 500 * duration / dist_diff
                    
                    if split_seconds < best_pace_seconds:
                        best_pace_seconds = split_seconds
                        
                        # Calculate normalized time for the exact target distance
                        # This avoids confusion where "Best 500m" shows time for 510m
                        normalized_duration = split_seconds * (target_dist_m / 500)
                        
                        m = int(normalized_duration // 60)
                        s = int(normalized_duration % 60)
                        
                        best_effort = {
                            "pace": calculate_split(dist_diff / duration),
                            "time": f"{m}:{s:02}",
                            "start_time": t_start_str,
                            "distance": round(dist_diff, 1)
                        }
            
            # Slide start window forward to find potentially tighter/faster segment
            start_idx += 1
        else:
            # Need more distance, expand window
            end_idx += 1
            
    return best_effort

def analyze_rowing(data, max_hr=190, resting_hr=60):
    """
    Perform specific rowing analysis.
    Recalculate average metrics for laps if they are missing/zero using record data.
    """
    session = data.get("session", {})
    laps = data.get("laps", [])
    records = data.get("records", [])
    
    # 500m Split calculation for Session
    avg_speed = session.get("avg_speed")
    session["avg_500m_split"] = calculate_split(avg_speed)
    
    # Pre-parse record timestamps for efficiency

    
    parsed_records = []
    for r in records:
        ts_str = r.get("timestamp")
        if ts_str:
            try:
                dt = datetime.datetime.fromisoformat(str(ts_str))
                parsed_records.append({"dt": dt, "data": r})
            except ValueError:
                continue

    # Auto-segmentation if laps are sparse (e.g. steady state as one lap)
    segmentation_type = "original"
    if len(laps) <= 1 and records:
        new_laps = auto_segment(records)
        if new_laps:
            laps = new_laps
            data["laps"] = laps
            segmentation_type = "auto_segmented"
    
    data["segmentation_type"] = segmentation_type

    # 500m Split calculation for Laps
    for i, lap in enumerate(laps):
        # Add index for display 1-based
        lap["lap_number"] = i + 1
        
        # Calculate speed - use avg_speed if available, otherwise calculate from distance/time
        lap_speed = lap.get("avg_speed")
        if not lap_speed or lap_speed == 0:
            # Fallback: calculate speed from distance and time
            dist = lap.get("total_distance", 0)
            time = lap.get("total_timer_time", 0)
            if dist > 0 and time > 0:
                lap_speed = dist / time
                lap["avg_speed"] = lap_speed  # Store for later use
        
        lap["avg_500m_split"] = calculate_split(lap_speed)
        
        # Check for missing/zero metrics
        metrics_to_fix = ["avg_cadence", "avg_heart_rate", "avg_power"]
        needs_fix = False
        for m in metrics_to_fix:
            val = lap.get(m)
            if val is None or val == 0:
                needs_fix = True
                break
        
        if needs_fix and lap.get("start_time") and lap.get("total_timer_time"):
            start_str = lap.get("start_time")
            try:
                start_dt = datetime.datetime.fromisoformat(str(start_str))
                duration_s = float(lap.get("total_timer_time"))
                end_dt = start_dt + datetime.timedelta(seconds=duration_s)
                
                # Filter records for this lap
                lap_records = [
                    x["data"] for x in parsed_records 
                    if x["dt"] >= start_dt and x["dt"] < end_dt
                ]
                
                if lap_records:
                    # Backfill cadence if missing or zero
                    if not lap.get("avg_cadence"):
                        vals = [float(r.get("cadence", 0)) for r in lap_records if r.get("cadence") is not None]
                        vals = [v for v in vals if v > 0]
                        if vals: lap["avg_cadence"] = round(sum(vals) / len(vals))
                        
                    # Backfill heart rate if missing or zero
                    if not lap.get("avg_heart_rate"):
                        vals = [float(r.get("heart_rate", 0)) for r in lap_records if r.get("heart_rate") is not None]
                        vals = [v for v in vals if v > 0]
                        if vals: lap["avg_heart_rate"] = round(sum(vals) / len(vals))

                    # Backfill power if missing or zero
                    if not lap.get("avg_power"):
                        vals = [float(r.get("power", 0)) for r in lap_records if r.get("power") is not None]
                        vals = [v for v in vals if v > 0]
                        if vals: lap["avg_power"] = round(sum(vals) / len(vals))
                        
            except ValueError:
                pass
        
        # Ensure key metrics exist even if None (for consistent JSON)
        metrics = ["total_distance", "total_timer_time", "avg_cadence", "avg_heart_rate", "avg_power"]
        for m in metrics:
            if m not in lap:
                lap[m] = None
                
    # Calculate Best Efforts
    # Use cleaned data for best splits (per Strategy C)
    cleaned_records = preprocess_records(records)
    
    data["analysis"] = {}
    data["analysis"]["best_500m"] = find_best_effort(cleaned_records, 500)
    data["analysis"]["best_1k"] = find_best_effort(cleaned_records, 1000)
    data["analysis"]["best_2k"] = find_best_effort(cleaned_records, 2000)
    data["analysis"]["best_4k"] = find_best_effort(cleaned_records, 4000)
    data["analysis"]["best_10k"] = find_best_effort(cleaned_records, 10000)

    # Store for Charting
    data["processed_records"] = cleaned_records

    # Calculate Location Name (Centralized Logic)
    start_lat = None
    start_lon = None
    
    # Check session
    if "start_position_lat" in session and "start_position_long" in session:
         start_lat = session["start_position_lat"]
         start_lon = session["start_position_long"]
    # Check records fallback
    if not start_lat:
         for r in records[:500]: # Check first 500 records
             if r.get("position_lat") and r.get("position_long"):
                 start_lat = r["position_lat"]
                 start_lon = r["position_long"]
                 break
                 
    if start_lat and start_lon:
        data["location_name"] = get_location_name(start_lat, start_lon)
    else:
        data["location_name"] = None

    # HR Analysis (New)
    hr_analysis = {
        "max_hr_observed": 0,
        "avg_hr_observed": 0,
        "resting_hr_observed": 0,
        "max_hr_config": max_hr,
        "resting_hr_config": resting_hr,
        "zones": {} # UT2, UT1, AT, TR, AN
    }

    # Ensure we use processed records for HR analysis if avail, else raw
    recs_for_hr = data.get("processed_records", records)
    valid_hrs = [float(r.get("heart_rate", 0) or 0) for r in recs_for_hr if r.get("heart_rate")]
    valid_hrs = [h for h in valid_hrs if h > 0]
    
    if valid_hrs:
        hr_analysis["max_hr_observed"] = int(max(valid_hrs))
        hr_analysis["avg_hr_observed"] = int(sum(valid_hrs) / len(valid_hrs))
        hr_analysis["resting_hr_observed"] = int(min(valid_hrs))

        # Zone Calculation (HRR)
        # Target = (Max - Rest) * % + Rest
        hr_reserve = max_hr - resting_hr
        
        zones_defs = {
            "UT2": (0.55, 0.70),
            "UT1": (0.70, 0.80),
            "AT":  (0.80, 0.85),
            "TR":  (0.85, 0.95),
            "AN":  (0.95, 1.00)
        }
        
        zone_counts = {k: 0 for k in zones_defs}
        
        for hr in valid_hrs:
            # Calculate intensity %
            if hr_reserve > 0:
                intensity = (hr - resting_hr) / hr_reserve
            else:
                intensity = 0
            
            # Determine zone
            matched = False
            for z_name, (low, high) in zones_defs.items():
                if low <= intensity < high:
                    zone_counts[z_name] += 1
                    matched = True
                    break
            
            # Handle values >= 100% or slightly above AN range
            if not matched:
                if intensity >= 0.95: 
                    zone_counts["AN"] += 1
                # Values below 0.55 are effectively "Warmup/Rest" not categorized
        
        total_valid = len(valid_hrs)
        for z_name in zones_defs: # Preserves order
            seconds = zone_counts[z_name]
            if total_valid > 0:
                pct = round((seconds / total_valid) * 100, 1)
            else:
                pct = 0
            m, s = divmod(seconds, 60)
            hr_analysis["zones"][z_name] = {
                "seconds": seconds,
                "percent": pct,
                "time_str": f"{m}:{s:02}"
            }
            
    data["heart_rate_analysis"] = hr_analysis

    return data

def preprocess_records(records):
    """
    Data Cleaning & Smoothing (Strategy C - Phase 1).
    1. Filter outliers (SPM > 60).
    2. Apply Moving Average smoothing (Window=5).
    """
    cleaned = []
    # 1. Outlier Removal
    for r in records:
        cad = float(r.get("cadence", 0) or 0)
        # Filter obvious bad data (but allow 0 for rest)
        if cad > 60:
            continue
        cleaned.append(r)
        
    if not cleaned: return []

    # 2. Moving Average Smoothing
    # We want to smooth Speed and Cadence
    window_size = 10
    smoothed = []
    
    n = len(cleaned)
    for i in range(n):
        # Determine window range [start, end]
        start = max(0, i - window_size // 2)
        end = min(n, i + window_size // 2 + 1)
        window = cleaned[start:end]
        
        # Calculate means
        speeds = [float(x.get("speed", 0) or 0) for x in window]
        cads = [float(x.get("cadence", 0) or 0) for x in window]
        
        avg_speed = sum(speeds) / len(speeds)
        avg_cad = sum(cads) / len(cads)
        
        # Create new record copy with smoothed values
        new_r = cleaned[i].copy()
        new_r["speed_smooth"] = avg_speed
        new_r["cadence_smooth"] = avg_cad
        
        # Parse timestamp for logic
        ts = new_r.get("timestamp")
        if ts:
             try:
                 new_r["dt"] = datetime.datetime.fromisoformat(str(ts))
             except:
                 continue
                 
        smoothed.append(new_r)
        
    return smoothed

def auto_segment(records):
    """
    Strategy C: Change Point Detection (CPD).
    Uses statistical divergence to identify segments.
    """
    # 1. Preprocess
    data = preprocess_records(records)
    if not data: return []
    
    # 2. CPD Logic
    segments = []
    current_segment = [data[0]]
    
    # Parameters for CPD
    # Threshold for speed change: 0.5 m/s shift triggers a cut
    # Or percentage change? Absolute is safer for rowing.
    CHANGE_THRESH = 0.4
    
    for i in range(1, len(data)):
        p = data[i]
        curr_speed = p["speed_smooth"]
        
        # Calculate stats of current segment so far
        # Optimization: Maintaining running sum would be faster, but len is small enough
        seg_speeds = [x["speed_smooth"] for x in current_segment]
        seg_mean = sum(seg_speeds) / len(seg_speeds)
        
        # Look at local trend (last 10 seconds / ~10 points)
        # If local trend diverges from segment mean, we have a change point
        local_window = data[max(0, i-10):i+1] # Look back a bit and include current
        local_speeds = [x["speed_smooth"] for x in local_window]
        local_mean = sum(local_speeds) / len(local_speeds)
        
        diff = abs(local_mean - seg_mean)
        
        # Trigger Split if:
        # 1. Divergence is high
        # 2. AND Segment is long enough (don't split immediately, allow 45s buffer)
        # Exception: If we drop to near zero speed (rest), allow split earlier
        is_stop = curr_speed < 1.0 and seg_mean > 2.0
        seg_duration = (current_segment[-1]["dt"] - current_segment[0]["dt"]).total_seconds()
        
        should_split = False
        if diff > 0.6: # Increased threshold from 0.4
             if seg_duration > 45:
                 should_split = True
             elif is_stop and seg_duration > 20:
                 should_split = True
        
        if should_split:
            # CHANGE DETECTED
            segments.append(current_segment)
            current_segment = [p]
        else:
            current_segment.append(p)
            
    if current_segment:
        segments.append(current_segment)
        
    # We still want to convert list-of-dicts to Laps
    # Note: create_lap_from_records expects "dt", "dist", "data". 
    # But our preprocessed data is flat. We need to adapt create_lap_from_records or map back.
    # Actually, our preprocessed 'data' HAS 'dt' and all fields.
    # BUT create_lap_from_records uses r["data"]... let's fix that adapter quickly below.
    
    laps = []
    for chunk in segments:
        # Adapt chunk to simpler format expected by helper, OR fix helper
        # Helper expects: { "dt": ..., "dist": ..., "data": {original} }
        # Our chunk is: { "dt": ..., "speed_smooth": ..., ...original fields... }
        
        # Let's map it for compatibility
        compat_chunk = []
        for r in chunk:
            compat_chunk.append({
                "dt": r["dt"],
                "dist": float(r.get("distance", 0)),
                "data": r, # Pass self as data source
                "speed": r["speed_smooth"] # Use smoothed speed for analysis? Or raw?
                # Use RAW for "Average Pace" reporting, but Smoothed was used for segmentation.
                # Let's pass raw data for metrics to be honest to the effort.
            })
        
        laps.append(create_lap_from_records(compat_chunk))
        
    # Filter noise
    laps = [l for l in laps if l.get("total_distance", 0) >= 100]
    
    return laps

def calculate_dps(speed_ms, spm):
    """Distance Per Stroke = Speed / (SPM / 60)."""
    if spm <= 0: return 0
    return speed_ms / (spm / 60)

def generate_coach_review(data):
    """
    Generate a basic rule-based coach review using session metrics.
    """
    # Extract Metrics
    metrics = data.get("analysis", {})
    laps = data.get("laps", [])
    session = data.get("session", {})
    
    total_dist = 0
    total_timer_time = 0
    total_elapsed = 0
    cad_prod = 0
    hr_prod = 0
    move_time = 0
    
    for l in laps:
        t = l.get("total_timer_time", 0)
        e = l.get("total_elapsed_time", 0)
        total_dist += l.get("total_distance", 0)
        total_elapsed += e
        
        # Only active laps for avg calc
        if l.get("type", "Work") != "Rest":
             move_time += t
             cad_prod += l.get("avg_cadence", 0) * t
             hr_prod += l.get("avg_heart_rate", 0) * t
             
    dist_km = total_dist / 1000
    avg_rate = int(cad_prod / move_time) if move_time > 0 else 0
    avg_hr = int(hr_prod / move_time) if move_time > 0 else 0
    
    # Construct Review
    lines = []
    lines.append(f"### 🎯 训练总结")
    lines.append(f"本次训练共完成 **{dist_km:.2f}km**，耗时 **{int(total_elapsed//60)}分钟**。")
    
    # Intensity Check
    if avg_rate < 20:
        intensity = "低桨频有氧 (UT2/UT1)"
        advice = "保持了良好的节奏控制，适合作为有氧耐力基础训练。"
    elif avg_rate < 26:
        intensity = "中高强度 (AT/TR)"
        advice = "桨频提升明显，注意在高桨频下保持技术动作的完整性。"
    else:
        intensity = "高强冲刺 (AN)"
        advice = "冲刺能力训练，注意每桨的实效性。"
        
    lines.append(f"整体属于 **{intensity}** 训练类别。")
    
    # HR Check
    if avg_hr > 0:
        lines.append(f"平均心率为 **{avg_hr}bpm**，请结合自身最大心率评估负荷。")
    
    lines.append(f"\n> 💡 **教练建议**: {advice}")
    lines.append(f"> 保持专注，继续积累里程！")

    return "\n".join(lines)

def export_analysis_json(data, input_file_path, max_hr=MAX_HR, resting_hr=RESTING_HR):
    """
    Export structured analysis data to JSON for LLM coach review.
    Returns the path to the exported JSON file.
    """
    # Prepare summary statistics
    laps = data.get("laps", [])
    session = data.get("session", {})
    analysis = data.get("analysis", {})
    
    # Detect if this is indoor rowing (Concept2 ERG)
    sub_sport = session.get("sub_sport", "")
    is_indoor = sub_sport == "indoor_rowing"
    
    # Calculate aggregate metrics
    steady_laps = [l for l in laps if l.get("total_distance", 0) > 300 and l.get("avg_speed", 0) > 1.5]
    dps_values = []
    pace_values = []
    cadence_values = []
    
    for l in steady_laps:
        s = l.get("avg_speed", 0)
        r = l.get("avg_cadence", 0)
        if r > 0:
            dps_values.append(s / (r/60))
        if s > 0:
            pace_values.append(500 / s)
        cadence_values.append(r)
    
    avg_dps = sum(dps_values)/len(dps_values) if dps_values else 0
    avg_pace = sum(pace_values)/len(pace_values) if pace_values else 0
    avg_cadence = sum(cadence_values)/len(cadence_values) if cadence_values else 0
    
    # Prepare analysis summary
    analysis_summary = {
        "session_info": {
            "total_distance_km": session.get("total_distance", 0) / 1000,
            "total_time_min": session.get("total_timer_time", 0) / 60,
            "start_time": session.get("start_time", ""),
            "location": data.get("location", "Unknown")
        },
        "aggregated_metrics": {
            "avg_dps": round(avg_dps, 1),
            "avg_pace_per_500m": round(avg_pace, 1),
            "avg_cadence": round(avg_cadence, 1),
            "num_segments": len(laps),
            "num_long_steady": len([l for l in laps if l.get("total_distance", 0) > 1500])
        },
        "segments": [
            {
                "number": l.get("lap_number", i+1),
                "distance_m": l.get("total_distance", 0),
                "time_sec": l.get("total_timer_time", 0),
                "avg_pace": l.get("avg_500m_split", "N/A"),
                "avg_cadence": l.get("avg_cadence", 0),
                "avg_heart_rate": l.get("avg_heart_rate", 0),
                "dps": round(l.get("avg_speed", 0) / (l.get("avg_cadence", 0) / 60), 1) if l.get("avg_cadence", 0) > 0 else "N/A",
                "type": l.get("segment_type", "Unknown")
            }
            for i, l in enumerate(laps)
        ],
        "best_efforts": {
            "best_500m": analysis.get("best_500m", {}),
            "best_1k": analysis.get("best_1k", {}),
            "best_2k": analysis.get("best_2k", {}),
            "best_4k": analysis.get("best_4k", {}),
            "best_10k": analysis.get("best_10k", {})
        },
        "heart_rate_analysis": data.get("heart_rate_analysis", {}),
        # Include Raw Data for Regeneration
        "laps": laps,
        "session": session,
        "processed_records": data.get("processed_records", []),
        "location_name": data.get("location_name")
    }
    
    # --- INDOOR REST DETECTION ---
    # Concept2 FIT files use the `intensity` field in lap messages to indicate work/rest.
    # Values like 'rest', 'recovery', 'warmup', 'cooldown' indicate non-work intervals.
    # We prioritize this field, falling back to speed heuristic if not available.
    processed_laps = []
    for lap in data.get("laps", []):
        is_rest = False
        
        # Method 1: Check FIT intensity field (most accurate)
        intensity = lap.get("intensity")
        if intensity is not None:
            # Common FIT intensity values: 'active', 'rest', 'warmup', 'cooldown', 'recovery'
            # Treat non-'active' as rest for interval workouts
            intensity_str = str(intensity).lower()
            if intensity_str in ["rest", "recovery", "warmup", "cooldown"]:
                is_rest = True
            elif intensity_str == "active":
                is_rest = False
            # If intensity is an enum/int, try to interpret:
            # 0=active, 1=rest, 2=warmup, 3=cooldown, 4=recovery (FIT SDK standard)
            elif isinstance(intensity, int):
                is_rest = intensity != 0  # Anything other than 0 (active) is considered rest
        else:
            # Method 2: Speed heuristic fallback (if intensity field is missing)
            avg_speed = float(lap.get("avg_speed", 0) or 0)
            if avg_speed < 2.0:  # Slower than 4:10/500m
                is_rest = True
             
        lap["type"] = "Rest" if is_rest else "Work"
        processed_laps.append(lap)
        
    data["laps"] = processed_laps
    # -----------------------------
    
    # --- WORKOUT PHASE DETECTION (Indoor only) ---
    # For indoor rowing (ERG), analyze the entire workout to identify: Warm-up, Main Sets, Cool-down
    # For on-water rowing, skip this - just use Work/Rest from segmentation
    # Strategy:
    #   1. Find the first "Rest" lap - everything before is likely Warm-up
    #   2. Find the last "Work" lap in an interval pattern - everything after is Cool-down
    #   3. The interval section in between is Main Sets
    
    laps = data.get("laps", [])
    num_laps = len(laps)
    
    if is_indoor and num_laps > 0:
        # Find first rest lap index (marks end of warm-up)
        first_rest_idx = None
        for i, lap in enumerate(laps):
            if lap.get("type") == "Rest":
                first_rest_idx = i
                break
        
        # Find last rest lap index (marks end of main sets)
        last_rest_idx = None
        for i in range(num_laps - 1, -1, -1):
            if laps[i].get("type") == "Rest":
                last_rest_idx = i
                break
        
        # Assign phases for indoor rowing
        for i, lap in enumerate(laps):
            if lap.get("type") == "Rest":
                lap["phase"] = "Rest"
            elif first_rest_idx is not None and i < first_rest_idx:
                # Before first rest = Warm-up
                lap["phase"] = "Warm-up"
            elif last_rest_idx is not None and i > last_rest_idx:
                # After last rest = Cool-down
                lap["phase"] = "Cool-down"
            else:
                # Between first and last rest = Main Set (work intervals)
                lap["phase"] = "Main Set"
    else:
        # For on-water rowing, just use the type as-is (no phase detection)
        for lap in laps:
            lap["phase"] = lap.get("type", "Work")
    
    data["laps"] = laps
    # -------------------------------
    
    # Determine output path
    base_name = os.path.splitext(os.path.basename(input_file_path))[0]
    timestamp_str = session.get("start_time", "").replace(":", "").replace("-", "").split("T")
    if len(timestamp_str) >= 2:
        ts = timestamp_str[0] + "_" + timestamp_str[1][:4]
    else:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    
    output_dir = os.path.dirname(input_file_path)
    # os.makedirs(output_dir, exist_ok=True) # Directory of input file must exist
    
    json_path = os.path.join(output_dir, f"ANALYSIS_{ts}.json")
    
    # Custom encoder for datetime objects
    def json_serializer(obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(analysis_summary, f, indent=2, ensure_ascii=False, default=json_serializer)
    
    return json_path

def generate_pacing_chart(data, output_dir, file_prefix):
    """
    Generate a Pace & Cadence chart using Matplotlib.
    """
    if not MATPLOTLIB_AVAILABLE:
        print("Warning: matplotlib/pandas not installed. Skipping chart generation.")
        return None

    records = data.get("processed_records") # Use Strategy C cleaned data
    if not records:
         records = data.get("records", []) # Fallback

    if not records:
        return None

    # Prepare DataFrame
    df_data = []
    start_time = None
    
    for r in records:
        # Strategy C data has 'dt' (datetime) and 'speed_smooth', 'cadence_smooth'
        # Fallback raw data has 'timestamp' (str or dt), 'speed', 'cadence'
        
        dt = r.get("dt")
        if not dt:
             ts = r.get("timestamp")
             if ts:
                 if isinstance(ts, str):
                    dt = datetime.datetime.fromisoformat(ts)
                 else:
                    dt = ts
        
        dist = r.get("distance")
        
        # Prefer smoothed values if available
        speed = r.get("speed_smooth", r.get("speed"))
        cad = r.get("cadence_smooth", r.get("cadence"))
        
        if not dt or dist is None: continue
            
        if start_time is None: start_time = dt
        
        # Calculate Pace (min/500m)
        pace_sec = 0
        if speed and speed > 0.5: # Lower threshold to catch slow drills
             pace_sec = 500 / speed
        else:
             pace_sec = None
             
        df_data.append({
            "time": dt,
            "elapsed": (dt - start_time).total_seconds(),
            "distance": dist,
            "pace_sec": pace_sec,
            "cadence": cad if cad and cad > 0 else None
        })
        
    df = pd.DataFrame(df_data)
    if df.empty: return None

    # No extra rolling needed if using processed data, but strictly speaking Strategy C is 5-point.
    # We can plot directly.
    df["pace_smooth"] = df["pace_sec"]
    df["cad_smooth"] = df["cadence"]

    # Create Plot
    fig, ax1 = plt.subplots(figsize=(12, 7), dpi=150)
    
    # Style
    plt.style.use('seaborn-v0_8-whitegrid')
    ax1.set_facecolor('#f8f9fa')

    # Add Summary Text Box
    session = data.get("session", {})
    laps = data.get("laps", [])

    # Recalculate Totals from Laps (Trust our segmentation)
    if laps:
        calc_total_dist = sum([float(l.get("total_distance", 0)) for l in laps])
        calc_total_time = sum([float(l.get("total_timer_time", 0)) for l in laps])
        
        # Calculate Weighted Averages
        cad_sum = 0
        for l in laps:
            cad_sum += float(l.get("avg_cadence", 0)) * float(l.get("total_timer_time", 0))
            
        avg_cad_val = cad_sum / calc_total_time if calc_total_time > 0 else 0
        avg_speed_val = calc_total_dist / calc_total_time if calc_total_time > 0 else 0
        
        total_dist = calc_total_dist / 1000
        total_time = calc_total_time / 60
        avg_pace = calculate_split(avg_speed_val)
        avg_cad = int(avg_cad_val)
    else:
        # Fallback to session or DF
        total_dist = session.get("total_distance", 0) / 1000
        total_time = session.get("total_timer_time", 0) / 60
        avg_speed_sess = session.get("avg_speed", 0)
        avg_cad_sess = session.get("avg_cadence", 0)
        avg_pace = calculate_split(avg_speed_sess)
        avg_cad = int(avg_cad_sess) if not np.isnan(avg_cad_sess) else 0
    
    plt.subplots_adjust(top=0.95, bottom=0.15) # Reduce top margin since no summary
    

    
    # Plot Split (Pace) on Left Y-axis
    color = '#1f77b4' # Blue
    ax1.set_xlabel('Distance (m)')
    ax1.set_ylabel('Pace (min/500m)', color=color)
    
    # Invert Y axis for pace (lower is faster) and handle format
    # Only plot where we have valid pace
    valid_pace = df[df["pace_smooth"] > 0]
    ax1.plot(valid_pace["distance"], valid_pace["pace_smooth"], color=color, linewidth=1.5, label="Pace")
    
    # Format Y ticks as mm:ss
    def time_ticks(x, pos):
        if np.isnan(x): return ""
        m = int(x // 60)
        s = int(x % 60)
        return f"{m}:{s:02}"
        
    import matplotlib.ticker as ticker
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(time_ticks))
    ax1.tick_params(axis='y', labelcolor=color)
    
    # Set realistic limits (e.g. 1:30 to 4:00)
    # ax1.set_ylim(bottom=100, top=240) # 1:40 to 4:00
    ax1.invert_yaxis() # Faster pace (lower time) on top
    
    # Plot Cadence on Right Y-axis
    ax2 = ax1.twinx()  
    color2 = '#ff7f0e' # Orange
    ax2.set_ylabel('Cadence (spm)', color=color2)
    ax2.plot(df["distance"], df["cad_smooth"], color=color2, linewidth=1.5, alpha=0.7, label="Cadence")
    ax2.tick_params(axis='y', labelcolor=color2)
    ax2.grid(False) # Turn off grid for second axis to avoid clutter
    
    plt.title("", pad=0) # Clear default title loc
    
    fig.tight_layout()  
    
    # Check if indoor
    is_indoor = False
    if session.get("sub_sport") == "indoor_rowing":
        is_indoor = True
        
    colors = {}
    # Plot Best Efforts (Only for On-Water/Outdoor)
    # Plot Best Efforts (Only for On-Water/Outdoor)
    if not is_indoor:
        best_efforts = data.get("analysis", {})
        
        # Define Staggered Layout (Y-axis in Axes coordinates 0-1)
        # Increased spacing to avoid label overlap
        # Order: 500m (Top), 1k, 2k, 4k (Bottom)
        
        layout_config = {
            "best_500m": {"color": "red", "label": "500m", "y_pos": 0.36},
            "best_1k": {"color": "green", "label": "1k", "y_pos": 0.28},
            "best_2k": {"color": "blue", "label": "2k", "y_pos": 0.20},
            "best_4k": {"color": "purple", "label": "4k", "y_pos": 0.12},
            "best_10k": {"color": "orange", "label": "10k", "y_pos": 0.04}
        }

        
        # We need to map distance (X) to layout
        # Using ax1.plot with transform=ax1.get_xaxis_transform() allows:
        # X in Data coords, Y in Axes coords (0-1)
        trans = ax1.get_xaxis_transform()
    
        for key, info in layout_config.items():
            effort = best_efforts.get(key)
            if effort and effort.get("start_time"):
                start_str = effort["start_time"]
                eff_dist = effort.get("distance", 0)
                
                # Find start distance in dataframe
                try:
                    start_dt = datetime.datetime.fromisoformat(start_str)
                    
                    if start_dt >= df["time"].min() and start_dt <= df["time"].max():
                         idx = (df["time"] - start_dt).abs().idxmin()
                         start_dist_val = df.loc[idx, "distance"]
                         end_dist_val = start_dist_val + eff_dist
                         
                         y_val = info["y_pos"]
                         color = info["color"]
                         
                         # Draw Bar (Line)
                         ax1.plot([start_dist_val, end_dist_val], [y_val, y_val], 
                                  color=color, linewidth=4, transform=trans, 
                                  solid_capstyle='butt', alpha=0.8)
                         
                         # Add Label
                         mid_dist = (start_dist_val + end_dist_val) / 2
                         pace_str = effort.get("pace", "")
                         label_text = f"{info['label']}: {pace_str}"
                         
                         # Place label slightly above line
                         ax1.text(mid_dist, y_val + 0.015, label_text, 
                                  color=color, fontsize=12, fontweight='bold', ha='center', va='bottom',
                                  transform=trans)

                except Exception as e:
                    # print(f"Error plotting {key}: {e}")
                    pass


    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    
    return buf

def generate_share_image(data, chart_buffer, review_text, output_dir, file_prefix, custom_title=None):
    """
    Generate a social-media ready 'long screenshot' image.
    Vertical layout: Header -> Metrics Grid -> Chart -> Segments -> Coach Review
    """
    if not PIL_AVAILABLE:
        print("Warning: Pillow not installed. Skipping share image generation.")
        return None

    # Load Chart from Buffer
    chart_img = None
    if chart_buffer:
        try:
             chart_img = Image.open(chart_buffer)
        except Exception as e:
             print(f"Error loading chart from buffer: {e}")

    # --- CONFIG ---
    img_width = 1200  # Increased for Chinese text which is wider
    bg_color = "#FFFFFF"
    text_color = "#333333"
    accent_color = "#1f77b4" # Blue
    
    # Font Logic: Try multiple known Chinese fonts on macOS
    font_candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
    ]
    
    font_path = None
    for fp in font_candidates:
        if os.path.exists(fp):
            font_path = fp
            break
            
    if not font_path:
        font_path = "/System/Library/Fonts/Supplemental/Arial.ttf" # Final fallback
    
    try:
        font_title = ImageFont.truetype(font_path, 48)
        font_header = ImageFont.truetype(font_path, 36)
        font_body = ImageFont.truetype(font_path, 28)
        font_small = ImageFont.truetype(font_path, 24)
        font_metric_val = ImageFont.truetype(font_path, 64)
        font_metric_lbl = ImageFont.truetype(font_path, 24)
    except Exception as e:
        print(f"Warning: Failed to load font {font_path}: {e}")
        # Fallback to default if load fails
        font_title = ImageFont.load_default()
        font_header = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_metric_val = ImageFont.load_default()
        font_metric_lbl = ImageFont.load_default()

    padding = 40
    current_y = 60
    
    # 1. Canvas Calculation (Dynamic Height)
    # We'll draw on a temp canvas to measure or just estimate and resize?
    # Easier to build list of "blocks" then assemble, or just estimated height.
    # Let's estimate: 
    # Header (150) + Grid (250) + Chart (600) + Table (Header 50 + Rows * 40) + Review (Variable)
    
    # Let's start with a large canvas and crop later? Or grow?
    # Pillow doesn't support growing easily.
    # Let's Calculate Table Height
    laps = data.get("laps", [])
    table_height = 80 + len(laps) * 50
    
    # Approximate Review Height
    # We haven't generated review yet, but we can wrap text.
    # Let's assume max 1000px for review for now, we will crop or paste.
    
    # Ideally we draw to separate images and stack them.
    blocks = []
    
    # BLOCK 1: HEADER
    # Title, Date, Location
    session = data.get("session", {})
    blk_header = Image.new("RGB", (img_width, 250), bg_color)
    # d = ImageDraw.Draw(blk_header) # Replaced by Pilmoji
    
    # Detect Sport Type from GPS
    has_gps = False
    records = data.get("records", [])
    for r in records:
        if r.get("position_lat") or r.get("start_position_lat"):
            has_gps = True
            break
            
    if custom_title:
        title = custom_title
    else:
        sport_label = "On-Water Rowing" if has_gps else "Indoor Rowing"
        title = f"🚣‍♀️ {sport_label}"
    # Date
    date_str = "Unknown Date"
    ts = session.get("start_time")
    if ts:
        try:
           dt = datetime.datetime.fromisoformat(str(ts)) + datetime.timedelta(hours=8)
           date_str = dt.strftime("%Y.%m.%d %H:%M")
           title = f"{dt.strftime('%m/%d')} {title}"
        except: pass
    
    # Location
    loc = data.get("location_name", "") 
    
    with Pilmoji(blk_header) as pilmoji:
        pilmoji.text((padding, 40), title, font=font_title, fill=text_color)
        pilmoji.text((padding, 110), f"📅 {date_str}   📍 {loc if loc else 'Unknown Location'}", font=font_small, fill="#666666")
        
    # Draw decorative line (Standard ImageDraw is fine for lines, or Pilmoji exposes it?)
    # Pilmoji wraps ImageDraw, but let's use standard draw for shapes if needed, or just create a fresh draw for non-text.
    # Actually Pilmoji.text() is the main addition. For lines, we can still use ImageDraw.
    d_lines = ImageDraw.Draw(blk_header)
    d_lines.line([(padding, 160), (100, 160)], fill=accent_color, width=6)
    
    blocks.append(blk_header)
    
    # BLOCK 2: METRICS GRID
    # 3x2 Grid: 6 items
    blk_grid = Image.new("RGB", (img_width, 300), bg_color)
    d = ImageDraw.Draw(blk_grid)
    
    # Recalculate metrics from Laps (Trust our segmentation over Fit Header)
    total_dist = 0
    total_time = 0 # Moving time
    total_elapsed = 0 # Elapsed time
    total_time = 0
    accum_pace = 0
    accum_cad = 0
    
    # We use simple average for cadence, volume weighted for speed?
    # Actually, Total Dist / Total Time is best for Avg Speed.
    count = 0
    cad_sum = 0
    hr_sum = 0
    
    for l in laps:
        d_val = float(l.get("total_distance", 0))
        t_val = float(l.get("total_timer_time", 0))
        e_val = float(l.get("total_elapsed_time", 0))
        c_val = float(l.get("avg_cadence", 0))
        h_val = float(l.get("avg_heart_rate", 0) or 0)
        
        total_dist += d_val
        total_elapsed += e_val
        
        # Only add to Move Time if NOT Rest
        # Note: "Work" or None are considered active for safety
        if l.get("type", "Work") != "Rest":
             total_time += t_val
        
        if c_val > 0:
            cad_sum += (c_val * t_val) # Time-weighted cadence
        if h_val > 0:
            hr_sum += (h_val * t_val)
    
    dist_km = total_dist / 1000
    time_min = total_time / 60
    
    avg_spd = total_dist / total_time if total_time > 0 else 0
    avg_pace = calculate_split(avg_spd)
    
    avg_rate = 0
    if total_time > 0:
        avg_rate = int(cad_sum / total_time)
        
    avg_hr = 0
    if total_time > 0:
        avg_hr = int(hr_sum / total_time)
    
    elapsed_min = total_elapsed / 60

    metrics = [
        ("Total Dist (km)", f"{dist_km:.2f}"),
        ("Elapsed Time (min)", f"{elapsed_min:.1f}"),
        ("Move Time (min)", f"{time_min:.1f}"),
        ("Avg Pace /500m", f"{avg_pace}"),
        ("Avg Rate (spm)", f"{avg_rate}"),
        ("Avg HR (bpm)", f"{avg_hr}")
    ]
    
    col_w = (img_width - 2*padding) / 3
    row_h = 120
    
    with Pilmoji(blk_grid) as pilmoji:
        for i, (lbl, val) in enumerate(metrics):
            r = i // 3
            c = i % 3
            x = padding + c * col_w
            y = 20 + r * row_h
            
            pilmoji.text((x, y), val, font=font_metric_val, fill=text_color)
            pilmoji.text((x, y + 80), lbl, font=font_metric_lbl, fill="#888888")
        
    blocks.append(blk_grid)
    
    # BLOCK 3: CHART
    if chart_img:
        try:
            # Resize to fit width (leaving padding)
            target_w = img_width - 2 * padding
            ratio = target_w / chart_img.width
            target_h = int(chart_img.height * ratio)
            chart_img = chart_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            
            # create container
            blk_chart = Image.new("RGB", (img_width, target_h + 40), bg_color)
            blk_chart.paste(chart_img, (padding, 20))
            blocks.append(blk_chart)
        except Exception as e:
            print(f"Error processing chart image: {e}")
            
    # BLOCK 4: SEGMENTS TABLE
    blk_table = Image.new("RGB", (img_width, table_height + 100), bg_color)
    d = ImageDraw.Draw(blk_table)
    
    with Pilmoji(blk_table) as pilmoji:
        pilmoji.text((padding, 20), "📊 Segments", font=font_header, fill=text_color)
        
    # d.text((padding, 20), "📊 Segments", font=font_header, fill=text_color) # Replaced
    
    # Headers
    # Headers
    headers = ["#", "Time", "Dist", "Pace", "SPM", "HR", "DPS", "Type"]
    # Adjust for 1080 width (padding 40 each side = 1000px usable)
    #               #   Time  Dist  Pace  SPM  HR   DPS  Type
    col_widths = [80, 160, 140, 160, 100, 100, 120, 140]
    curr_x = padding
    header_y = 80
    
    for i, h in enumerate(headers):
        d.text((curr_x, header_y), h, font=font_small, fill="#888888")
        curr_x += col_widths[i]
        
    # Rows
    y = header_y + 50
    for i, lap in enumerate(laps):
        # Data prep - similar to report
        num = str(lap.get("lap_number", i+1))
        
        dur_s = lap.get("total_timer_time", 0)
        m = int(dur_s // 60)
        s = int(dur_s % 60)
        dur_str = f"{m}:{s:02}"
        if dur_s >= 3600:
             h = int(dur_s // 3600)
             m = int((dur_s % 3600) // 60)
             dur_str = f"{h}:{m:02}:{s:02}"
             
        dist_str = f"{int(lap.get('total_distance', 0))}m"
        pace = str(lap.get("avg_500m_split", "-"))
        spm = str(int(lap.get("avg_cadence", 0)))
        
        avg_spd = lap.get("avg_speed", 0)
        cad = lap.get("avg_cadence", 0)
        dps = avg_spd / (cad/60) if cad > 0 else 0
        dps_str = f"{dps:.1f}" if dps > 0 else "-"
        
        # Type / Zone
        l_type_raw = lap.get("type", "Work")
        if l_type_raw == "Rest":
            l_type = "Rest"
        else:
            # Consistent with Markdown report: Use HR/SPM classification
            # We need HR and SPM from lap
            hr_val = lap.get("avg_heart_rate", 0) or 0
            cad_val = int(lap.get("avg_cadence", 0))
            # Need max_hr/resting_hr... they are not passed to generate_share_image currently!
            # We need to default or pass them. 
            # Let's assume defaults for now if not passed, or default to MAX_HR/RESTING_HR constant globals
            l_type = classify_training_zone(hr_val, cad_val, MAX_HR, RESTING_HR)
            if not l_type: l_type = "Work"
            
        hr_str = str(int(lap.get("avg_heart_rate", 0) or 0))

        row_vals = [num, dur_str, dist_str, pace, spm, hr_str, dps_str, l_type]
        
        curr_x = padding
        # Alternating row color
        if i % 2 == 1:
            d.rectangle([(padding, y-10), (img_width-padding, y+35)], fill="#F8F9FA")
            
        for j, val in enumerate(row_vals):
            d.text((curr_x, y), val, font=font_body, fill=text_color)
            curr_x += col_widths[j]
            
        y += 50
        
    blocks.append(blk_table)
    
    # BLOCK 5: COACH REVIEW
    # Use passed review text (which matches Markdown report)
    if not review_text:
         review_text = "Coach Review Pending..."
         

    # Markdown-Lite Renderer
    lines_to_draw = [] # (text, font, color, x_offset, y_padding_top)
    
    # Pre-process markdown lines
    raw_lines = review_text.split('\n')
    
    # 1. Measurement & Parsing
    simulated_y = 0
    
    def get_text_width(text, font):
        if hasattr(font, 'getlength'):
            return font.getlength(text)
        else:
            return font.getsize(text)[0]

    def wrap_text(txt, font, max_width):
        # Pixel-based wrapping for accurate multi-lingual support
        if not txt: return []
        
        words = []
        # For Chinese, we might want to treat every character as a word roughly, 
        # or just split by standard spaces if mixed.
        # A simple strategy: split by space, but if a segment is huge (likely Chinese without spaces), 
        # split it character by character.
        
        # Simple comprehensive split that preserves existing spaces but allows splitting CJK
        import re
        # This regex matches: spaces, OR non-ascii characters (CJK), OR normal words
        # patterns: \s+, [^\x00-\x7F], \S+
        # But keeping it simple: just iterate chars if it's mostly non-ascii?
        # Let's stick to a robust char-by-char accumulation if we are mixed.
        
        lines = []
        current_line = ""
        current_w = 0
        
        # Naive char-by-char wrapping is safest for mixed CJK/English without complex logic
        # Optimization: group words by space?
        # Let's use a dual approach: Split by space first.
        
        raw_words = txt.split(' ')
        for i, w in enumerate(raw_words):
             # Restore the space if it wasn't the last word
             suffix = " " if i < len(raw_words) - 1 else ""
             word_with_space = w + suffix
             
             w_width = get_text_width(word_with_space, font)
             
             if current_w + w_width <= max_width:
                 current_line += word_with_space
                 current_w += w_width
             else:
                 # If the single word is wider than the line (and it's not empty), we must split it (e.g. long Chinese sentence)
                 if get_text_width(w, font) > max_width:
                     # Hard split for very long tokens (like CJK sentences without spaces)
                     # Push current line if valid
                     if current_line:
                         lines.append(current_line)
                         current_line = ""
                         current_w = 0
                     
                     # Char-by-char fill
                     for char in word_with_space:
                         cw = get_text_width(char, font)
                         if current_w + cw <= max_width:
                             current_line += char
                             current_w += cw
                         else:
                             lines.append(current_line)
                             current_line = char
                             current_w = cw
                 else:
                     # Normal wrap
                     lines.append(current_line)
                     current_line = word_with_space
                     current_w = w_width
                     
        if current_line:
            lines.append(current_line)
            
        return lines

    for line in raw_lines:
        line = line.strip()
        if not line:
            # Paragraph Break - larger gap between sections
            lines_to_draw.append(("", None, None, 0, 30)) # 30px spacer
            continue
        
        # Skip the main "## Coach Review" header since we draw our own title
        if line.startswith("## "):
            continue
            
        if line.startswith("### "):
            # Header - use accent color with emoji preserved
            txt = line.replace("### ", "").replace("**", "")
            wrapped = wrap_text(txt, font_header, img_width - 2*padding)  # Full width
            for i, wl in enumerate(wrapped):
                pad = 25 if i == 0 else 5  # Space before header, tight for wrapped
                lines_to_draw.append((wl, font_header, accent_color, 0, pad))
        
        elif line.startswith("* ") or line.startswith("- "):
            # Bullet - consistent indentation with clean formatting
            txt = line[2:].replace("**", "")  # Remove bullet markers and bold
            wrapped = wrap_text("• " + txt, font_body, img_width - 2*padding - 20)  # Slight indent for bullet
            for i, wl in enumerate(wrapped):
                x_off = 10  # Consistent indent for all lines
                if i > 0:
                    wl = "  " + wl.lstrip()  # Indent continuation without extra bullet
                pad = 8 if i == 0 else 3
                lines_to_draw.append((wl, font_body, "#333333", x_off, pad))
                
        elif line.startswith("> "):
            # Quote - styled with left border effect (indent + italic color)
            txt = line.replace("> ", "").replace("**", "")  # Remove quote marker
            wrapped = wrap_text(txt, font_body, img_width - 2*padding - 40)  # Indent for quote border
            for i, wl in enumerate(wrapped):
                pad = 20 if i == 0 else 8
                lines_to_draw.append((wl, font_body, "#1f77b4", 30, pad))  # Blue quote
        else:
            # Body text
            txt = line.replace("**", "")
            wrapped = wrap_text(txt, font_body, img_width - 2*padding)
            for i, wl in enumerate(wrapped):
                pad = 10 if i == 0 else 6
                lines_to_draw.append((wl, font_body, "#444444", 0, pad))
                
    # 2. Canvas Calculation
    # Measure total height - comfortable line heights
    total_review_h = 100 # Title + buffer
    for txt, fnt, col, x, pad in lines_to_draw:
        h = 28  # Tighter body line height
        if fnt == font_header: h = 38  # Header line height
        if not txt: h = 0 # spacer only padding
        total_review_h += h + pad
        
    # Add minimal buffer at bottom
    blk_review = Image.new("RGB", (img_width, total_review_h + 50), bg_color)
    d_rev_lines = ImageDraw.Draw(blk_review)
    # d_rev = ImageDraw.Draw(blk_review) # Replaced
    
    with Pilmoji(blk_review) as pilmoji:
        # Draw Title
        pilmoji.text((padding, 40), "👨‍🏫 Coach Review", font=font_header, fill=text_color)
        d_rev_lines.line([(padding, 90), (padding + 300, 90)], fill="#EEEEEE", width=4)
        
        curr_y = 100
        for txt, fnt, col, x, pad in lines_to_draw:
            curr_y += pad
            if txt:
                pilmoji.text((padding + x, curr_y), txt, font=fnt, fill=col)
                line_h = 28  # Match the calculation above
                if fnt == font_header: line_h = 38
                curr_y += line_h
    
    blocks.append(blk_review)
    
    total_h = sum(b.height for b in blocks)
    final_img = Image.new("RGB", (img_width, total_h + 60), bg_color)  # Just enough for footer
    
    curr_y = 0
    for b in blocks:
        final_img.paste(b, (0, curr_y))
        curr_y += b.height
        
    # Footer
    d_foot = ImageDraw.Draw(final_img)
    # Use Pilmoji for footer too regarding the Robot emoji
    with Pilmoji(final_img) as pilmoji:
        pilmoji.text((padding, total_h + 20), "Generated by Rowing Coach AI 🤖", font=font_small, fill="#CCCCCC")
    
    # Save
    share_path = os.path.join(output_dir, f"{file_prefix}_SHARE.png")
    final_img.save(share_path)
    return share_path

def generate_training_report(data, input_file_path, max_hr_val, resting_hr_val, forced_review=None):
    """
    Generates a Markdown training report.
    If forced_review is provided, it uses that text instead of extracting from existing file or generating placeholder.
    """
    session = data.get("session", {})
    laps = data.get("laps", [])

    # Calculate Totals from Laps (more accurate for segmented data)
    calc_total_dist = sum([l.get("total_distance", 0) for l in laps])
    calc_total_time = sum([l.get("total_timer_time", 0) for l in laps])
    total_dist_km = calc_total_dist / 1000
    
    # 1. Determine Prefix (ROW/ERG)
    is_indoor = False
    if session.get("sub_sport") == "indoor_rowing":
        is_indoor = True
    
    has_gps = False
    if "start_position_lat" in session:
        has_gps = True
    elif laps and laps[0].get("start_position_lat"):
        # Sometimes session doesn't have it but lap does
        has_gps = True
    else:
        # Check records
        for r in data.get("records", [])[:100]: # Check first 100
            if r.get("position_lat"):
                has_gps = True
                break
    
    prefix = "ERG"
    if has_gps:
       prefix = "ROW"
    elif not is_indoor and "SpdCoach" in input_file_path:
       # SpdCoach files without GPS (indoor mode?) or just SpdCoach
       prefix = "ROW" 

    # 2. Determine Timestamp
    # 2. Determine Timestamp
    # Ensure datetime is imported if not at top level, though it should be.
    import datetime 
    
    start_t = session.get("start_time")
    file_time_str = "UNKNOWN_DATE"
    if start_t:
        try:
            if isinstance(start_t, datetime.datetime):
                dt_utc = start_t
            else:
                dt_utc = datetime.datetime.fromisoformat(str(start_t))
            
            # Localize
            dt_local = dt_utc + datetime.timedelta(hours=8)
            file_time_str = dt_local.strftime("%Y%m%d_%H%M")
        except Exception as e:
            pass
    
    base_filename = f"{prefix}_{file_time_str}"
    output_filename = f"{base_filename}.md"
    
    # Save to the SAME directory as the input file
    output_dir = os.path.dirname(os.path.abspath(input_file_path))
    
    # Generate Chart (In-Memory)
    chart_buffer = None

    if MATPLOTLIB_AVAILABLE:
        # Pass the exact base filename as prefix
        chart_buffer = generate_pacing_chart(data, output_dir, base_filename)
        
    output_path = os.path.join(output_dir, output_filename)

    # --- PRESERVE EXISTING COACH REVIEW ---
    existing_review = None
    if os.path.exists(output_path):
         try:
             with open(output_path, 'r', encoding='utf-8') as old_f:
                 content = old_f.read()
                 # Relaxed match
                 header_str = "## 👨‍🏫 教练点评 (Coach Review)"
                 s_idx = content.find(header_str)
                 
                 if s_idx != -1:
                     # Start after header + whitespace
                     sub_start = s_idx + len(header_str)
                     sub = content[sub_start:].lstrip()
                     
                     # Look for next section header or horizontal rule
                     import re
                     match = re.search(r'\n(## |---)' , sub)
                     if match:
                         existing_review = sub[:match.start()].strip()
                     else:
                         # No next header or rule, take until end of file
                         existing_review = sub.strip()
                     
                     # Check if it is valid (not placeholder)
                     if existing_review and "等待 LLM 教练分析中" in existing_review:
                         existing_review = None
         except Exception as e:
             # print(f"Warning: Could not read existing file: {e}")
             pass
    # --------------------------------------

    
    # TITLE GENERATION
    if is_indoor:
        type_name = "Indoor Rowing"
    else:
        type_name = "On-Water Rowing"

    title_main = f"🚣‍♀️ {type_name} | {total_dist_km:.1f}km Full Analysis 🌊"
    image_title = f"🚣‍♀️ {type_name}"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {title_main}\n\n")
        
        # Add Training Time Info
        if session.get("start_time"):
            try:
                dt = datetime.datetime.fromisoformat(str(session.get("start_time")))
                # FIT uses UTC. Convert to UTC+8 (Beijing Time)
                dt_local = dt + datetime.timedelta(hours=8)
                time_str = dt_local.strftime("%Y-%m-%d %H:%M")
                f.write(f"> 📅  **训练时间**: {time_str}\n\n")
            except:
                pass

        # Add Location Info
        # Find first valid coordinates
        start_lat = None
        start_lon = None
        
        # Check session first
        if "start_position_lat" in session and "start_position_long" in session:
             start_lat = session["start_position_lat"]
             start_lon = session["start_position_long"]

        # Fallback to records
        if not start_lat:
             records = data.get("records", [])
             for r in records:
                 if r.get("position_lat") and r.get("position_long"):
                     start_lat = r["position_lat"]
                     start_lon = r["position_long"]
                     break
                     
        if start_lat and start_lon:
            # location_name is already calculated in analyze_rowing now, but get_location_name is cached/cheap?
            # Let's rely on data['location_name'] if available, else calc
            loc_name = data.get("location_name")
            if not loc_name:
                 loc_name = get_location_name(start_lat, start_lon)
            
            if loc_name:
                f.write(f"> 📍  **训练地点**: {loc_name}\n\n")

        # Basic Data Summary (Moved here)
        f.write("## 📝 基础数据汇总\n\n")
        
        # Calculate Averages (Weighted by time for accuracy)
        avg_cad_val = 0
        cad_prod_sum = 0
        hr_prod_sum = 0
        
        calc_elapsed_time = 0
        calc_move_time = 0
        avg_cad_val = 0
        avg_hr_val = 0
        avg_speed_val = 0
        
        if laps:
            for l in laps:
                t = l.get("total_timer_time", 0)
                e = l.get("total_elapsed_time", 0)
                
                calc_elapsed_time += e
                if l.get("type", "Work") != "Rest":
                    calc_move_time += t
                    
                cad_prod_sum += l.get("avg_cadence", 0) * t
                hr_prod_sum += l.get("avg_heart_rate", 0) * t
            
            if calc_move_time > 0:
                avg_cad_val = int(cad_prod_sum / calc_move_time)
                avg_hr_val = int(hr_prod_sum / calc_move_time)
                avg_speed_val = calc_total_dist / calc_move_time
            else:
                 avg_speed_val = 0
                 
        avg_pace_str = calculate_split(avg_speed_val)

        f.write(f"**总距离**: {total_dist_km:.2f} km\n")
        f.write(f"**总时间 (Elapsed)**: {calc_elapsed_time/60:.1f} min\n")
        f.write(f"**运动时间 (Move)**: {calc_move_time/60:.1f} min\n")
        f.write(f"**平均配速**: {avg_pace_str} /500m\n")
        f.write(f"**平均桨频**: {avg_cad_val} spm\n")
        f.write(f"**平均心率**: {avg_hr_val} bpm\n")
        
        f.write("\n---\n")
        
        # REMOVED Chart Section as requested
        
        f.write("## 📊  Full Segments\n\n")
        f.write("| # | Time | Distance | Pace/500m | SPM | HR | DPS | Note |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        
        for i, lap in enumerate(laps):
            num = lap.get("lap_number", i+1)
            
            # Duration format mm:ss
            dur_s = lap.get("total_timer_time", 0)
            m = int(dur_s // 60)
            s = int(dur_s % 60)
            dur_str = f"{m}:{s:02}"
            
            # Remove "0:" prefix if hours present (simple logic)
            if dur_s >= 3600:
                h = int(dur_s // 3600)
                m = int((dur_s % 3600) // 60)
                dur_str = f"{h}:{m:02}:{s:02}"
            
            dist = lap.get("total_distance", 0)
            pace = lap.get("avg_500m_split", "-")
            cad = lap.get("avg_cadence", 0) or 0
            hr = lap.get("avg_heart_rate", 0) or 0
            avg_spd = lap.get("avg_speed", 0)
            
            # DPS
            dps = calculate_dps(avg_spd, cad) if cad > 0 else 0
            dps_str = f"{dps:.1f}m" if dps > 0 else "-"
            
            # HR display
            hr_str = str(int(hr)) if hr > 0 else "-"
            
            # Classify intervals based on SPM and HR
            is_rest = lap.get("type") == "Rest"
            if is_rest:
                note = "Rest"
            else:
                # Use new centralized classification function
                note = classify_training_zone(hr, cad, max_hr_val, resting_hr_val)
            
            # No special formatting - plain table row
            row_str = f"| {num} | {dur_str} | {int(dist)}m | {pace} | {cad} | {hr_str} | {dps_str} | {note} |"
            f.write(row_str + "\n")
            
        f.write("\n---\n")
        
        # Add generated Chart if available


        if not is_indoor:
            f.write("## 🏆 最佳表现 (Best Efforts)\n\n")
            
            best_500 = data.get("analysis", {}).get("best_500m")
            best_1k = data.get("analysis", {}).get("best_1k")
            best_2k = data.get("analysis", {}).get("best_2k")
            best_4k = data.get("analysis", {}).get("best_4k")
            best_10k = data.get("analysis", {}).get("best_10k")
            
            if best_500: f.write(f"*   **最快 500m**: `{best_500['pace']}` (用时 {best_500['time']})\n")
            if best_1k: f.write(f"*   **最快 1000m**: `{best_1k['pace']}` (用时 {best_1k['time']})\n")
            if best_2k: f.write(f"*   **最快 2000m**: `{best_2k['pace']}` (用时 {best_2k['time']})\n")
            if best_4k: f.write(f"*   **最快 4000m**: `{best_4k['pace']}` (用时 {best_4k['time']})\n")
            if best_10k: f.write(f"*   **最快 10000m**: `{best_10k['pace']}` (用时 {best_10k['time']})\n")
                
            if not any([best_500, best_1k, best_2k, best_4k, best_10k]):
                f.write("数据不足，无法计算最佳分段。\n")
                
            f.write("\n---\n")
        f.write("## 👨‍🏫 教练点评 (Coach Review)\n\n")
        
        # Expert System Review
        if forced_review:
             f.write(forced_review + "\n\n")
             print(f"Using provided Coach Review via CLI arguments.", file=sys.stderr)
             final_review = forced_review
        elif existing_review:
             f.write(existing_review + "\n\n")
             print(f"Preserved existing Coach Review for {output_filename}", file=sys.stderr)
             final_review = existing_review
        else:
             coach_comment = generate_coach_review(data)
             f.write(coach_comment + "\n\n")
             final_review = coach_comment
        
        f.write("\n---\n")

        
    return output_path, chart_buffer, final_review, image_title

def main():
    parser = argparse.ArgumentParser(description="Parse FIT file for Rowing Coach analysis.")
    
    parser.add_argument("file_path", nargs='?', help="Path to the FIT file")
    parser.add_argument("--max-hr", type=int, default=MAX_HR, help="Maximum Heart Rate")
    parser.add_argument("--resting-hr", type=int, default=RESTING_HR, help="Resting Heart Rate")
    parser.add_argument("--regen-share", metavar="MD_FILE", help="Regenerate share image from existing markdown report")
    
    args = parser.parse_args()

    # Mode: Regenerate share image from existing report
    if args.regen_share:
        md_path = args.regen_share
        if not os.path.exists(md_path):
            print(f"Error: Markdown file not found: {md_path}")
            sys.exit(1)
        
        # Find corresponding JSON file
        md_dir = os.path.dirname(md_path) or "."
        md_base = os.path.basename(md_path)
        
        # Extract timestamp from filename (e.g., ERG_20260120_2117.md -> 20260120)
        import re
        match = re.search(r'(\d{8})_(\d{4})', md_base)
        if not match:
            print(f"Error: Cannot extract timestamp from filename: {md_base}")
            sys.exit(1)
        
        # Find matching JSON file
        json_files = [f for f in os.listdir(md_dir) if f.startswith('ANALYSIS_') and f.endswith('.json')]
        json_path = None
        for jf in json_files:
            if match.group(1) in jf:
                json_path = os.path.join(md_dir, jf)
                break
        
        if not json_path or not os.path.exists(json_path):
            print(f"Error: Cannot find matching JSON file for {md_base}")
            sys.exit(1)
        
        # Load JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # Extract review text from markdown
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()

        # Extract Title from Markdown (first line: # 🚣‍♀️ Title | ...)
        custom_header = None
        # Look for first line starting with #
        first_line_end = md_content.find('\n')
        if first_line_end != -1:
            first_line = md_content[:first_line_end]
            # Simple split by |
            if '|' in first_line:
                parts = first_line.split('|')
                # Take part before | and remove #
                custom_header = parts[0].replace('#', '').strip()
            
        
        review_start = md_content.find("## 👨‍🏫 教练点评")
        if review_start == -1:
            review_start = md_content.find("## Coach Review")
        
        review_text = ""
        if review_start != -1:
            review_section = md_content[review_start:]
            # Find end (next --- or end of file)
            review_end = review_section.find("\n---")
            if review_end != -1:
                review_text = review_section[:review_end].strip()
            else:
                review_text = review_section.strip()
        
        # Convert datetime strings back to datetime objects in processed_records
        processed_records = json_data.get('processed_records', [])
        for rec in processed_records:
            if 'dt' in rec and isinstance(rec['dt'], str):
                try:
                    rec['dt'] = datetime.datetime.fromisoformat(rec['dt'])
                except:
                    pass
        
        # Reconstruct analyzed_data from JSON for chart generation
        analyzed_data = {
            'session': json_data.get('session', {}),
            'laps': json_data.get('laps', []),
            'processed_records': processed_records,
            'location_name': json_data.get('location_name'),
            'analysis': {
                'best_500m': json_data.get('best_efforts', {}).get('best_500m', {}),
                'best_1k': json_data.get('best_efforts', {}).get('best_1k', {}),
                'best_2k': json_data.get('best_efforts', {}).get('best_2k', {}),
                'best_4k': json_data.get('best_efforts', {}).get('best_4k', {}),
                'best_10k': json_data.get('best_efforts', {}).get('best_10k', {}),
            },
            'heart_rate_analysis': json_data.get('heart_rate_analysis', {}),
        }
        
        # Generate chart
        f_prefix = os.path.splitext(md_base)[0]
        chart_buffer = generate_pacing_chart(analyzed_data, md_dir, f_prefix)
        
        # Generate share image
        if chart_buffer:
            share_path = generate_share_image(analyzed_data, chart_buffer, review_text, md_dir, f_prefix, custom_title=custom_header)
            print(f"✅ Share image regenerated: {share_path}")
        else:
            print("⚠️ Could not generate chart (missing processed_records in JSON)")
        
        sys.exit(0)

    # Normal mode: Parse FIT file
    if not args.file_path:
        parser.error("file_path is required unless using --regen-share")
    
    parsed_data = parse_fit(args.file_path)
    
    if parsed_data:
        analyzed_data = analyze_rowing(parsed_data, args.max_hr, args.resting_hr)
        
        # Export analysis JSON (Keep this as an artifact)
        json_path = export_analysis_json(analyzed_data, args.file_path, args.max_hr, args.resting_hr)
        print(f"✅ Analysis JSON generated: {json_path}")

        # Generate Report
        post_path, chart_buffer, review_text, image_title = generate_training_report(analyzed_data, args.file_path, args.max_hr, args.resting_hr)
        
        # Generate Share Image
        share_path = None
        if post_path and chart_buffer:
             md_name = os.path.basename(post_path)
             f_prefix = os.path.splitext(md_name)[0]
             share_path = generate_share_image(analyzed_data, chart_buffer, review_text, os.path.dirname(post_path), f_prefix, custom_title=image_title)

        print(f"\n✅ 报告生成完成！")
        print(f"📝 Markdown: {post_path}")
        if share_path:
            print(f"🖼️ Share Image: {share_path}")

    else:
        sys.exit(1)

if __name__ == "__main__":
    main()

