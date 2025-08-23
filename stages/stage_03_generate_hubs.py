# stages/stage_03_generate_hubs.py
# -*- coding: utf-8 -*-
"""Stage 03 — Compute per-station throat hubs and axis.

Reads:
  - data/processed/station_info_master.csv

Writes:
  - data/processed/station_throat_hubs.json
  - (optional) data/processed/station_axis.csv

Validations:
  - Warn if a station has only one side (West/East) hubs -> axis missing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

from utils.constants import PROCESSED_DIR, STATION_HELPER_FILE
from utils.layout_ops import (
    build_throat_hubs_for_station,
    estimate_station_axis_from_hubs,
    hubs_to_serializable,
)


def _setup_logger(debug_mode: bool = False) -> logging.Logger:
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    return logger


def run(debug: bool = False) -> None:
    """Main entrypoint for Stage 03."""
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

    station_df = pd.read_csv(station_csv, delimiter=";")

    # --- Outputs
    hubs_json_path = PROCESSED_DIR / "station_throat_hubs.json"
    axis_csv_path = PROCESSED_DIR / "station_axis.csv"

    hubs_all: Dict[str, Dict] = {}
    axis_rows = []

    for i, row in station_df.iterrows():
        station = str(row.get("station", f"idx_{i}"))
        try:
            hubs = build_throat_hubs_for_station(row)
            hubs_all[station] = hubs_to_serializable(hubs)

            axis_vec: Optional[Tuple[float, float]] = estimate_station_axis_from_hubs(
                hubs
            )
            if axis_vec is None:
                logger.warning(
                    "⚠️ Axis could not be estimated for station %s (one side missing).",
                    station,
                )
                axis_rows.append({"station": station, "vx": "", "vy": ""})
            else:
                axis_rows.append(
                    {
                        "station": station,
                        "vx": round(axis_vec[0], 3),
                        "vy": round(axis_vec[1], 3),
                    }
                )
        except Exception as e:
            logger.error("Failed computing hubs for station %s: %s", station, e)
            continue

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

    logger.info("🏁 Stage 03 completed.")
