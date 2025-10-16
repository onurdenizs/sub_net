# stages/stage_00_prepare_master.py
# -*- coding: utf-8 -*-
"""Stage 00 — Prepare master station info.

Reads:
  - utils.constants.POLYGON_FILE (linie_mit_polygon.csv)
  - utils.constants.PLATFORM_FILE (perronkante.csv)

Writes:
  - utils.constants.STATION_MASTER_FILE (CSV, UTF-8 with BOM)
  - data/processed/stage00_validation_report.txt

This stage aggregates per-station metadata:
- platform length stats (min/max/avg and a decided length)
- inferred platform_count (fallbacks applied when missing)
- participating line_ids
- connected_stations separated by West/East
- center_coordinates sampled from line geometries (endpoints touching the station)
"""

from __future__ import annotations

import json
import logging
from typing import List, Set, Tuple

import pandas as pd

from utils.constants import (
    DEFAULT_PLATFORM_COUNT,
    DEFAULT_PLATFORM_LENGTH,
    FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH,
    FILL_EMPTY_PLATFORM_NO_DATA_WITH,
    LINE_ID_LIST,
    MAX_PLATFORM_COUNT,
    MAX_PLATFORM_LENGTH,
    MIN_PLATFORM_COUNT,
    MIN_PLATFORM_LENGTH,
    NEVER_SKIP_LIST,
    PLATFORM_FILE,
    PLATFORM_LENGTH_DECISION_METHOD,
    POLYGON_FILE,
    PROCESSED_DIR,
    STATION_MASTER_FILE,
)
from utils.segment_ops import parse_geo_shape


def setup_logger(debug_mode: bool = False) -> logging.Logger:
    """Configure and return a module logger.

    Args:
      debug_mode: If True, set level to DEBUG; otherwise INFO.

    Returns:
      A configured logger instance.
    """
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    return logger


def get_fallback_values() -> Tuple[float, int]:
    """Return fallback platform length and count based on constants policy.

    Returns:
      (platform_length_m, platform_count) honoring the fill strategies.
    """
    if FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH == "X":
        platform_length = MAX_PLATFORM_LENGTH
    elif FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH == "N":
        platform_length = MIN_PLATFORM_LENGTH
    else:
        platform_length = DEFAULT_PLATFORM_LENGTH

    if FILL_EMPTY_PLATFORM_NO_DATA_WITH == "X":
        platform_count = MAX_PLATFORM_COUNT
    elif FILL_EMPTY_PLATFORM_NO_DATA_WITH == "N":
        platform_count = MIN_PLATFORM_COUNT
    else:
        platform_count = DEFAULT_PLATFORM_COUNT

    return float(platform_length), int(platform_count)


def decide_platform_length(min_len: float, max_len: float, avg_len: float) -> float:
    """Choose a representative platform length according to decision policy.

    Args:
      min_len: Minimum observed platform length for the station (m).
      max_len: Maximum observed platform length for the station (m).
      avg_len: Average observed platform length for the station (m).

    Returns:
      A single decided platform length (m).
    """
    if PLATFORM_LENGTH_DECISION_METHOD == "X":
        return min(MAX_PLATFORM_LENGTH, max_len)
    elif PLATFORM_LENGTH_DECISION_METHOD == "N":
        return max(MIN_PLATFORM_LENGTH, min_len)
    elif PLATFORM_LENGTH_DECISION_METHOD == "A":
        return max(MIN_PLATFORM_LENGTH, min(MAX_PLATFORM_LENGTH, avg_len))
    else:
        return DEFAULT_PLATFORM_LENGTH


def validate_master_data(
    master_df: pd.DataFrame, stations_set: Set[str], logger: logging.Logger
) -> None:
    """Run basic sanity checks and dump a short validation report.

    Args:
      master_df: Produced master DataFrame.
      stations_set: Set of known station codes from polygon file.
      logger: Logger for messages.

    Side effects:
      Writes a text report under PROCESSED_DIR.
    """
    report_lines: List[str] = []
    error_count = 0

    logger.info("🔎 Starting Stage 00 validation...")

    # 1) NaN scan
    if master_df.isnull().values.any():
        count = int(master_df.isnull().sum().sum())
        report_lines.append(f"⚠️ Found {count} missing (NaN) values in master_df.")
        error_count += count

    # 2) center_coordinates structure
    for idx, row in master_df.iterrows():
        centers = row["center_coordinates"]
        if not isinstance(centers, list):
            try:
                centers = json.loads(str(centers).replace("'", '"'))
            except Exception:
                report_lines.append(
                    f"❌ Row {idx} station {row['station']} has invalid center_coordinates format."
                )
                error_count += 1
                continue
        if not all(isinstance(c, list) and len(c) == 2 for c in centers):
            report_lines.append(
                f"❌ Row {idx} station {row['station']} has malformed center_coordinates."
            )
            error_count += 1

    # 3) line_ids whitelist
    allowed_line_ids = set(LINE_ID_LIST)
    for idx, row in master_df.iterrows():
        line_ids = row["line_ids"]
        if isinstance(line_ids, str):
            try:
                line_ids = json.loads(line_ids.replace("'", '"'))
            except Exception:
                report_lines.append(
                    f"❌ Row {idx} station {row['station']} has non-JSON line_ids."
                )
                error_count += 1
                continue
        unexpected = set(line_ids) - allowed_line_ids
        if unexpected:
            report_lines.append(
                f"❌ Station {row['station']} has unexpected line_ids: {unexpected}"
            )
            error_count += len(unexpected)

    # 4) connected_stations known?
    for idx, row in master_df.iterrows():
        connected = row["connected_stations"]
        if isinstance(connected, str):
            try:
                connected = json.loads(connected.replace("'", '"'))
            except Exception:
                report_lines.append(
                    f"❌ Row {idx} station {row['station']} has non-JSON connected_stations."
                )
                error_count += 1
                continue
        for direction in ("West", "East"):
            unknown_stations = set(connected.get(direction, [])) - stations_set
            if unknown_stations:
                report_lines.append(
                    f"❌ Station {row['station']} has unknown {direction} connections: {unknown_stations}"
                )
                error_count += len(unknown_stations)

    # 5) numeric sanity
    numeric_cols = [
        "min_platform_length",
        "max_platform_length",
        "avg_platform_length",
        "decided_platform_length",
        "platform_count",
    ]
    for col in numeric_cols:
        negatives = master_df[col] < 0
        if getattr(negatives, "any", lambda: False)():
            count = int(negatives.sum())
            report_lines.append(f"❌ Column {col} has {count} negative values.")
            error_count += count

    # 6) never-skip coverage
    missing_never_skip = set(NEVER_SKIP_LIST) - stations_set
    if missing_never_skip:
        report_lines.append(
            f"❌ Missing stations from NEVER_SKIP_LIST: {missing_never_skip}"
        )
        error_count += len(missing_never_skip)

    # Summary line
    if error_count == 0:
        report_lines.append("✅ Stage 00 validation passed. No critical issues found.")
    else:
        report_lines.append(
            f"⚠️ Stage 00 validation completed with {error_count} issue(s)."
        )

    # Emit to logger
    for line in report_lines:
        if "❌" in line or "⚠️" in line:
            logger.warning(line)
        else:
            logger.info(line)

    # Persist report
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    report_path = PROCESSED_DIR / "stage00_validation_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    logger.info("📄 Validation report saved to: %s", report_path.resolve())


def run(debug: bool = False) -> None:
    """Entry point for Stage 00.

    Args:
      debug: If True, enable verbose logging.
    """
    logger = setup_logger(debug)
    logger.info("🚀 Stage 00 started: Prepare master station info")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # --- Load inputs
    try:
        polygon_df = pd.read_csv(POLYGON_FILE, delimiter=";")
        perron_df = pd.read_csv(PLATFORM_FILE, delimiter=";")
    except FileNotFoundError as e:
        logger.error("❌ Input file not found: %s", e)
        return
    except Exception as e:
        logger.error("❌ Failed to read input CSVs: %s", e)
        return

    # Limit to configured line IDs
    polygon_df = polygon_df[polygon_df["Linie"].isin(LINE_ID_LIST)].copy()
    stations: Set[str] = set(polygon_df["START_OP"]).union(polygon_df["END_OP"])

    master_rows = []
    for station in stations:
        # Gather perronkante stats for this station
        station_perron = perron_df[perron_df["Station abbreviation"] == station]
        lengths = station_perron["Length of platform edge"].dropna().tolist()
        if lengths:
            min_len = float(min(lengths))
            max_len = float(max(lengths))
            avg_len = float(sum(lengths) / len(lengths))
            platform_count = len(set(station_perron["Platform number"].dropna()))
        else:
            min_len = max_len = avg_len = None
            platform_count = None

        if min_len is None:
            # No platform info → fallbacks
            platform_length, platform_count = get_fallback_values()
            min_len = max_len = avg_len = platform_length
        else:
            platform_length = decide_platform_length(min_len, max_len, avg_len)
            platform_count = max(
                MIN_PLATFORM_COUNT, min(MAX_PLATFORM_COUNT, int(platform_count))
            )

        # Collect involved line IDs
        line_ids = sorted(
            set(
                polygon_df[
                    (polygon_df["START_OP"] == station)
                    | (polygon_df["END_OP"] == station)
                ]["Linie"].tolist()
            )
        )

        # Build connection sets and representative center coords
        connected_stations = {"West": set(), "East": set()}
        center_coordinates: Set[Tuple[float, float]] = set()

        for _, seg in polygon_df.iterrows():
            start_op = seg["START_OP"]
            end_op = seg["END_OP"]
            coords = parse_geo_shape(seg["Geo shape"])
            if not coords or len(coords) < 2:
                continue

            if start_op == station:
                # Segment leaves this station towards "East" direction
                connected_stations["East"].add(end_op)
                center_coordinates.add(tuple(coords[0]))  # near the station
            if end_op == station:
                # Segment arrives to this station from "West" direction
                connected_stations["West"].add(start_op)
                center_coordinates.add(tuple(coords[-1]))  # near the station

        master_rows.append(
            {
                "station": station,
                "min_platform_length": min_len,
                "max_platform_length": max_len,
                "avg_platform_length": avg_len,
                "decided_platform_length": platform_length,
                "platform_count": platform_count,
                "line_ids": line_ids,  # list is fine in CSV; validation tolerates JSON str too
                "connected_stations": {
                    k: list(v) for k, v in connected_stations.items()
                },
                "center_coordinates": [list(c) for c in center_coordinates],
            }
        )

    master_df = pd.DataFrame(master_rows)

    # Keep behavior: stringify connected_stations as JSON for compactness
    master_df["connected_stations"] = master_df["connected_stations"].apply(json.dumps)

    # Persist output
    master_df.to_csv(STATION_MASTER_FILE, index=False, encoding="utf-8-sig")
    logger.info("✅ Saved master station info to: %s", STATION_MASTER_FILE.resolve())

    # Post validations
    validate_master_data(master_df, stations, logger)
