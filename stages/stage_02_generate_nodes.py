# -*- coding: utf-8 -*-
"""
Stage 02 — Build station info & entry nodes.

Reads:
  - data/processed/filtered_sub_network_data.csv  (from Stage 01)
  - data/raw/perronkante.csv                       (platform edges)

Writes:
  - data/processed/station_info_master.csv

What it does:
  1) Filters platform rows to only stations in the filtered sub-network.
  2) Builds per-station metrics (min/max/avg/decided platform length, platform count, line_ids).
  3) Infers connected stations and their directions (West/East).
  4) Classifies station types: two-way / single-direction / isolated.
  5) Places entry nodes on line segments using a distance offset from the station end.

Run (only Stage 02 via pipeline):
  python run_pipeline.py --start 2 --end 2 --debug
"""

from __future__ import annotations

import logging
from typing import Set

import pandas as pd

from utils.constants import (
    FILTERED_SUB_NETWORK_POLYGON_FILE,
    NEVER_SKIP_LIST,
    PLATFORM_FILE,
    PROCESSED_DIR,
    STATION_HELPER_FILE,
)
from utils.platform_ops import (
    build_station_info,
    define_station_types,
    filter_perron_data,
    find_entry_nodes,
    find_station_connections,
)


# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
def _setup_logger(debug_mode: bool = False) -> logging.Logger:
    """Create a simple stream logger."""
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    return logger


# ------------------------------------------------------------------------------
# Stage 02 runner
# ------------------------------------------------------------------------------
def run(debug: bool = False) -> None:
    """Execute Stage 02."""
    logger = _setup_logger(debug)
    logger.info("🚀 Stage 02 started: Generate station info")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    success = False
    try:
        # 1) Load data
        polygon_df = pd.read_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, delimiter=";")
        perron_df = pd.read_csv(PLATFORM_FILE, delimiter=";")
        logger.info(
            "📥 Loaded polygon: %s (%d rows)",
            FILTERED_SUB_NETWORK_POLYGON_FILE,
            len(polygon_df),
        )
        logger.info(
            "📥 Loaded perronkante: %s (%d rows)", PLATFORM_FILE, len(perron_df)
        )

        # 2) Limit perron data to stations present in polygon_df
        unique_ops: Set[str] = set(polygon_df["START_OP"]).union(polygon_df["END_OP"])
        perron_df_filtered = filter_perron_data(perron_df, unique_ops)
        logger.info("🔎 Unique stations in polygon: %d", len(unique_ops))
        logger.info("🔎 Filtered perronkante rows: %d", len(perron_df_filtered))

        # 3) Build per-station platform info (lengths, counts, line_ids)
        station_info_df = build_station_info(polygon_df, perron_df_filtered, logger)

        # 4) Add connected stations & direction (West/East)
        station_info_df = find_station_connections(station_info_df, polygon_df, logger)

        # 5) Classify station type
        station_info_df = define_station_types(station_info_df)

        # 6) Compute entry nodes from polygon segments
        station_info_df = find_entry_nodes(station_info_df, polygon_df, logger)

        # 7) Save stable output for downstream stages
        station_info_df.sort_values(by="station", inplace=True)
        station_info_df.to_csv(
            STATION_HELPER_FILE, index=False, sep=";", encoding="utf-8-sig"
        )
        logger.info("✅ Saved station info CSV → %s", STATION_HELPER_FILE.resolve())
        success = True

    except Exception as e:
        logger.error("❌ Stage 02 failed: %s", e)

    # --------------------------------------------------------------------------
    # Final validations (only if we reached a valid dataframe)
    # --------------------------------------------------------------------------
    if not success:
        logger.warning("⚠️ Skipping validations because Stage 02 did not complete.")
        return

    logger.info("\n🔎 Performing final validations...")

    # 1) Number of stations should match between polygon & platform summary
    polygon_unique_stations = set(polygon_df["START_OP"]).union(polygon_df["END_OP"])
    platform_unique_stations = set(station_info_df["station"])
    if len(polygon_unique_stations) != len(platform_unique_stations):
        logger.warning(
            "⚠️ 1️⃣ Number of stations validation FAILED " "(polygon=%d vs platform=%d)",
            len(polygon_unique_stations),
            len(platform_unique_stations),
        )
    else:
        logger.info("✅ Number of stations validation PASSED")

    # 2) NEVER_SKIP_LIST presence
    missing_never_skip = set(NEVER_SKIP_LIST) - polygon_unique_stations
    if missing_never_skip:
        logger.warning(
            "⚠️ NEVER_SKIP_LIST stations missing in final data: %s", missing_never_skip
        )
    else:
        logger.info("✅ All NEVER_SKIP_LIST stations present.")

    # 3) Isolated stations
    isolated_stations = set(
        station_info_df[station_info_df["type"] == "isolated"]["station"]
    )
    if isolated_stations:
        logger.warning(
            "⚠️ ISOLATED STATION VALIDATION: %d isolated station(s) found.",
            len(isolated_stations),
        )
        for idx, sta in enumerate(sorted(isolated_stations), start=1):
            logger.warning("   #%d %s", idx, sta)
    else:
        logger.info("✅ ISOLATED STATION VALIDATION PASSED")

    # 4) Entry node count matches number of connections
    mismatches = []
    for _, row in station_info_df.iterrows():
        conn_dict = row["connected_stations"]
        expected_count = sum(len(v) for v in conn_dict.values())
        actual_count = len(row["entry_nodes"])
        if expected_count != actual_count:
            mismatches.append(
                {
                    "Station": row["station"],
                    "Expected": expected_count,
                    "Actual": actual_count,
                }
            )

    if mismatches:
        logger.warning(
            "⚠️ %d stations with mismatched entry-node count:", len(mismatches)
        )
        for m in mismatches:
            logger.warning(
                "   %s: Expected %d but found %d",
                m["Station"],
                m["Expected"],
                m["Actual"],
            )
    else:
        logger.info("✅ All stations have correct number of entry nodes.")

    logger.info("✅ STAGE 02 VALIDATION complete.")
