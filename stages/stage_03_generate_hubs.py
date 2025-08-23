# stages/stage_03_generate_hubs.py
# -*- coding: utf-8 -*-
"""Stage 03 — Compute per-station throat hubs and axis.

Reads:
  - data/processed/station_info_master.csv
  - data/processed/filtered_sub_network_data.csv  (for single-side axis fallback)

Writes:
  - data/processed/station_throat_hubs.json
  - data/processed/station_axis.csv

Validations:
  - Warn if a station has only one side (West/East) hubs -> vector axis missing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

import utils.constants as C
from utils.constants import (
    FILTERED_SUB_NETWORK_POLYGON_FILE,
    PROCESSED_DIR,
    STATION_HELPER_FILE,
)
from utils.layout_ops import (
    build_throat_hubs_for_station,
    estimate_station_axis_from_hubs,
    estimate_station_axis_line_from_hubs,
    hubs_to_serializable,
)


def _setup_logger(debug_mode: bool = False) -> logging.Logger:
    """Configure a module-level logger.

    Args:
        debug_mode: If True, set level to DEBUG, else INFO.

    Returns:
        Configured logger.
    """
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    return logger


def _get_min_axis_length() -> float:
    """Read minimal axis length from constants (fallback 200.0)."""
    return float(getattr(C, "STATION_AXIS_MIN_LENGTH", 200.0))


def run(debug: bool = False) -> None:
    """Main entrypoint for Stage 03.

    Steps:
        1) Load station info (Stage 02 output) and filtered segments.
        2) For each station, cluster entry nodes into West/East hubs.
        3) Compute axis vector (vx, vy) if both sides exist.
        4) Compute axis line (x1, y1, x2, y2) with single-side fallback
           using PCA or segment-derived heading.
        5) Write hubs JSON and axis CSV.

    Args:
        debug: Enable verbose logging if True.
    """
    logger = _setup_logger(debug)
    logger.info("🚀 Stage 03 started: Compute throat hubs & station axis")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # --- Load station info (Stage 02 output)
    station_csv = Path(STATION_HELPER_FILE)
    if not station_csv.exists():
        logger.error(
            "❌ station_info_master.csv not found at %s", station_csv.resolve()
        )
        return

    try:
        station_df = pd.read_csv(station_csv, delimiter=";")
    except Exception as e:
        logger.error("❌ Failed to read station info CSV: %s", e)
        return

    # --- Load filtered segments for single-side axis fallback
    segment_csv = Path(FILTERED_SUB_NETWORK_POLYGON_FILE)
    segment_df: Optional[pd.DataFrame]
    try:
        segment_df = pd.read_csv(segment_csv, delimiter=";")
    except Exception as e:
        logger.warning(
            "⚠️ Could not read filtered_sub_network_data.csv for axis fallback: %s", e
        )
        segment_df = None

    # --- Outputs
    hubs_json_path = PROCESSED_DIR / "station_throat_hubs.json"
    axis_csv_path = PROCESSED_DIR / "station_axis.csv"

    hubs_all: Dict[str, Dict] = {}
    axis_rows = []

    min_axis_len = _get_min_axis_length()
    missing_vec = 0
    missing_line = 0

    for i, row in station_df.iterrows():
        station = str(row.get("station", f"idx_{i}")).strip()
        try:
            # 1) Hubs
            hubs = build_throat_hubs_for_station(row)
            hubs_all[station] = hubs_to_serializable(hubs)

            # 2) Axis vector (West→East) — both sides required
            axis_vec: Optional[Tuple[float, float]] = estimate_station_axis_from_hubs(
                hubs
            )
            if axis_vec is None:
                missing_vec += 1
                logger.warning(
                    "⚠️ Axis vector could not be estimated for %s (one side missing).",
                    station,
                )
                vx, vy = "", ""
            else:
                vx, vy = round(axis_vec[0], 3), round(axis_vec[1], 3)

            # 3) Axis line (robust; single-side fallback via PCA/segments)
            axis_line = estimate_station_axis_line_from_hubs(
                station=station,
                hubs=hubs,
                logger=logger,
                min_axis_length=min_axis_len,
                segment_df=segment_df,
            )
            if axis_line is None:
                missing_line += 1
                x1 = y1 = x2 = y2 = ""
            else:
                x1, y1, x2, y2 = (
                    round(axis_line[0], 3),
                    round(axis_line[1], 3),
                    round(axis_line[2], 3),
                    round(axis_line[3], 3),
                )

            axis_rows.append(
                {
                    "station": station,
                    "vx": vx,
                    "vy": vy,
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                }
            )
        except Exception as e:
            logger.error("❌ Failed computing hubs/axis for %s: %s", station, e)
            axis_rows.append(
                {
                    "station": station,
                    "vx": "",
                    "vy": "",
                    "x1": "",
                    "y1": "",
                    "x2": "",
                    "y2": "",
                }
            )

    # --- Write JSON (hubs)
    try:
        with open(hubs_json_path, "w", encoding="utf-8") as f:
            json.dump(hubs_all, f, ensure_ascii=False, indent=2)
        logger.info("✅ Saved hubs JSON: %s", hubs_json_path.resolve())
    except Exception as e:
        logger.error("❌ Failed writing hubs JSON: %s", e)

    # --- Write CSV (axis)
    try:
        axis_df = pd.DataFrame(axis_rows)
        axis_df.sort_values("station", inplace=True)
        axis_df.to_csv(axis_csv_path, index=False, sep=";", encoding="utf-8-sig")
        logger.info("✅ Saved axis CSV: %s", axis_csv_path.resolve())
    except Exception as e:
        logger.error("❌ Failed writing axis CSV: %s", e)

    # --- Summary
    total = len(station_df)
    logger.info(
        "ℹ️ Axis summary: %d stations total | %d missing vector | %d missing line",
        total,
        missing_vec,
        missing_line,
    )
    logger.info("🏁 Stage 03 completed.")
