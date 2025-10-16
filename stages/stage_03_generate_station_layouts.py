# stages/stage_03_generate_station_layouts.py
# -*- coding: utf-8 -*-
"""
Stage 03 — Build a minimal station design master CSV.

Outputs (semicolon-separated):
  utils.constants.STATION_DESIGN_FILE  ->  data/processed/station_design_master.csv
  Columns:
    - station
    - number_of_tracks            (from station_info.platform_count)
    - platform_length             (from station_info.decided_platform_length)
    - reference_point_coordinates (computed here as [x, y])
    - ref_x                       (float)
    - ref_y                       (float)
    - layout_type                 (from decide_main_station_layout)
    - generated_at                (ISO datetime)
    - stage_version               (str)
    - source_files                (JSON string)

Inputs:
  - FILTERED_SUB_NETWORK_POLYGON_FILE: segments CSV with START_OP, END_OP, _coordinates
  - STATION_HELPER_FILE              : station info CSV with at least
                                       station, platform_count, decided_platform_length, entry_nodes
"""

from __future__ import annotations

import ast
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from utils.constants import (
    FILTERED_SUB_NETWORK_POLYGON_FILE,
    PROCESSED_DIR,
    STATION_DESIGN_FILE,
    STATION_HELPER_FILE,
)
from utils.layout_ops import decide_main_station_layout

STAGE_VERSION = "03.2"


# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
def _setup_logger(debug: bool = False) -> logging.Logger:
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(h)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    return logger


def _bool_from_env(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


# -----------------------------------------------------------------------------
# Helpers for anchor (reference point)
# -----------------------------------------------------------------------------
def _as_coords(obj) -> List[Tuple[float, float]]:
    """Convert Stage-01 `_coordinates` to a Python list of (x, y) floats."""
    if isinstance(obj, list):
        return [(float(x), float(y)) for x, y in obj]
    if isinstance(obj, str):
        s = obj.strip()
        try:
            return [(float(x), float(y)) for x, y in json.loads(s)]
        except Exception:
            return [(float(x), float(y)) for x, y in ast.literal_eval(s)]
    raise ValueError("Unsupported `_coordinates` cell type")


def _compute_anchor_for_station(
    station: str, segs: pd.DataFrame
) -> Dict[str, Any] | None:
    """Compute one reference point for `station` from touching segment endpoints."""
    pts: List[Tuple[float, float]] = []

    west_df = segs[segs["END_OP"] == station]
    east_df = segs[segs["START_OP"] == station]

    for _, row in west_df.iterrows():
        coords = _as_coords(row["_coordinates"])
        if coords:
            pts.append(tuple(coords[-1]))  # END side at the station

    for _, row in east_df.iterrows():
        coords = _as_coords(row["_coordinates"])
        if coords:
            pts.append(tuple(coords[0]))  # START side at the station

    if not pts:
        return None

    xs = np.array([p[0] for p in pts], dtype=float)
    ys = np.array([p[1] for p in pts], dtype=float)
    ax = float(xs.mean())
    ay = float(ys.mean())

    # RMSE around the anchor as a quick spread metric (not exported now)
    d2 = (xs - ax) ** 2 + (ys - ay) ** 2
    _ = float(np.sqrt(d2.mean())) if len(pts) > 0 else 0.0

    return {"station": station, "x": ax, "y": ay}


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------
def _is_missing(value: Any) -> bool:
    """Robust 'missing' check for mixed types (None/NaN/empty string/empty list/tuple/dict)."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except Exception:
        pass
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, tuple, dict)) and len(value) == 0:
        return True
    return False


def _validate_and_report(
    info_df: pd.DataFrame,
    out_df: pd.DataFrame,
    layout_dist: Dict[str, int],
    report_path: str,
    logger: logging.Logger,
) -> Dict[str, Any]:
    """Validate the output and log + write a concise English report.

    Returns a dict with booleans about issues for optional fail-fast.
    """
    input_rows = int(len(info_df))
    output_rows = int(len(out_df))
    row_match = input_rows == output_rows

    required_cols = [
        "station",
        "number_of_tracks",
        "platform_length",
        "reference_point_coordinates",
        "layout_type",
        "ref_x",
        "ref_y",
    ]

    # Per-column missing counts
    missing_by_col: Dict[str, int] = {}
    for col in required_cols:
        if col not in out_df.columns:
            missing_by_col[col] = output_rows  # entirely missing
            continue
        missing_mask = out_df[col].apply(_is_missing)
        missing_by_col[col] = int(missing_mask.sum())

    # Stations with any missing required field
    any_missing_mask = pd.DataFrame(
        {
            col: out_df[col].apply(_is_missing) if col in out_df.columns else True
            for col in required_cols
        }
    ).any(axis=1)
    stations_with_missing = out_df.loc[any_missing_mask, "station"].astype(str).tolist()
    n_missing_stations = len(stations_with_missing)

    # Build the report text
    lines: List[str] = []
    lines.append("── Validation report — Station Design Master ──")
    lines.append(f"Input stations read    : {input_rows}")
    lines.append(f"Output stations written: {output_rows}")
    lines.append(f"Row count match        : {'YES' if row_match else 'NO'}")
    lines.append("Missing values by column:")
    for col in required_cols:
        lines.append(f"  - {col}: {missing_by_col.get(col, 0)}")
    if layout_dist:
        lines.append("Layout type distribution:")
        for k, v in sorted(layout_dist.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"  - {k}: {v}")
    if n_missing_stations > 0:
        preview = stations_with_missing[:20]
        extra = n_missing_stations - len(preview)
        tail = f" (+{extra} more)" if extra > 0 else ""
        lines.append(
            f"Stations with missing values ({n_missing_stations}): {', '.join(preview)}{tail}"
        )
    else:
        if row_match and all(cnt == 0 for cnt in missing_by_col.values()):
            lines.append(
                "All stations and required columns are populated; no missing values detected."
            )
        else:
            lines.append(
                "No station has missing values, but row count mismatch detected."
            )  # rare

    report = "\n".join(lines)

    # Log and write report
    logger.info("\n%s", report)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report + "\n")

    return {
        "row_match": row_match,
        "n_missing_stations": n_missing_stations,
        "missing_by_col": missing_by_col,
    }


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def run(debug: bool = False) -> None:
    logger = _setup_logger(debug)
    logger.info("🚀 Stage 03 started: station_design_master builder")

    # Ensure output directory exists
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # --- Load inputs (semicolon-separated)
    seg = pd.read_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, sep=";")
    info = pd.read_csv(STATION_HELPER_FILE, sep=";", dtype={"entry_nodes": "object"})

    # --- Validate required columns
    required_seg = {"START_OP", "END_OP", "_coordinates"}
    missing_seg = required_seg - set(seg.columns)
    if missing_seg:
        logger.error("❌ Missing columns in segments file: %s", sorted(missing_seg))
        return

    required_info = {
        "station",
        "platform_count",
        "decided_platform_length",
        "entry_nodes",
    }
    missing_info = required_info - set(info.columns)
    if missing_info:
        logger.error(
            "❌ Missing columns in station info file: %s", sorted(missing_info)
        )
        return

    logger.info("📥 Segments: %d rows | Station info: %d rows", len(seg), len(info))

    # --- Compute reference points for all stations (keep stations even if no endpoints)
    anchor_rows: List[Dict[str, Any]] = []
    for station in info["station"].astype(str):
        touching = seg[(seg["START_OP"] == station) | (seg["END_OP"] == station)]
        rec = (
            _compute_anchor_for_station(station, touching)
            if not touching.empty
            else None
        )
        if rec:
            anchor_rows.append(rec)

    anchors_df = (
        pd.DataFrame(anchor_rows)
        if anchor_rows
        else pd.DataFrame(columns=["station", "x", "y"])
    )

    # --- Decide layout_type per row using entry_nodes
    layout_series = info.apply(
        lambda r: decide_main_station_layout(r).get("layout_type", "unknown"), axis=1
    )

    # --- Assemble output with requested columns only
    out = (
        info[["station", "platform_count", "decided_platform_length"]]
        .rename(
            columns={
                "platform_count": "number_of_tracks",
                "decided_platform_length": "platform_length",
            }
        )
        .merge(anchors_df, on="station", how="left")
    )

    # reference point as list and separate x,y
    def _pack_ref(row):
        x, y = row.get("x"), row.get("y")
        if pd.notna(x) and pd.notna(y):
            return [float(x), float(y)]
        return None

    out["reference_point_coordinates"] = out.apply(_pack_ref, axis=1)
    out["ref_x"] = out["x"].astype(float) if "x" in out.columns else np.nan
    out["ref_y"] = out["y"].astype(float) if "y" in out.columns else np.nan
    out.drop(columns=[c for c in ["x", "y"] if c in out.columns], inplace=True)

    out["layout_type"] = layout_series

    # meta columns
    generated_at = datetime.now().isoformat(timespec="seconds")
    source_files = {
        "segments": str(FILTERED_SUB_NETWORK_POLYGON_FILE),
        "station_info": str(STATION_HELPER_FILE),
    }
    out["generated_at"] = generated_at
    out["stage_version"] = STAGE_VERSION
    out["source_files"] = json.dumps(source_files, ensure_ascii=False)

    # Keep only requested columns (and in the requested order + meta)
    out = out[
        [
            "station",
            "number_of_tracks",
            "platform_length",
            "reference_point_coordinates",
            "ref_x",
            "ref_y",
            "layout_type",
            "generated_at",
            "stage_version",
            "source_files",
        ]
    ]

    # --- Write to constants path
    out.to_csv(STATION_DESIGN_FILE, sep=";", index=False, encoding="utf-8-sig")
    logger.info("✅ Saved: %s", STATION_DESIGN_FILE.resolve())

    # --- Distribution & Validation report
    layout_dist = out["layout_type"].value_counts(dropna=False).to_dict()
    report_path = str((PROCESSED_DIR / "station_design_master_report.txt").resolve())
    verdict = _validate_and_report(
        info_df=info,
        out_df=out,
        layout_dist=layout_dist,
        report_path=report_path,
        logger=logger,
    )

    # --- Optional fail-fast via env var
    fail_fast = _bool_from_env("STAGE03_FAIL_FAST", default=False)
    if fail_fast:
        has_row_issue = not verdict["row_match"]
        has_missing_issue = verdict["n_missing_stations"] > 0
        if has_row_issue or has_missing_issue:
            logger.error(
                "❌ Fail-fast enabled and issues detected. Exiting with code 1."
            )
            raise SystemExit(1)

    logger.info("🏁 Stage 03 completed.")


if __name__ == "__main__":
    run(debug=False)
