# -*- coding: utf-8 -*-
"""
Stage 01 — Clean and analyze line segment geometries.

Reads:
  - data/raw/linie_mit_polygon.csv

Writes:
  - data/processed/filtered_sub_network_data.csv

What it does:
  1) Filters to the configured LINE_ID_LIST.
  2) Parses each segment's GeoJSON-like "Geo shape" into coordinate arrays.
  3) Computes length and point-count per segment.
  4) For each line (Linie), walks segments in KM order and:
     - merges/removes segments shorter than CLOSENESS_THRESHOLD,
     - respects NEVER_SKIP_LIST so certain stations are preserved,
     - re-evaluates after merges to avoid chain-short leftovers.
  5) Saves the cleaned subset and runs simple validations.

Run (only Stage 01 via pipeline):
  python run_pipeline.py --start 1 --end 1 --debug
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import pandas as pd

from utils.constants import CLOSENESS_THRESHOLD, FILTERED_SUB_NETWORK_POLYGON_FILE
from utils.constants import LINE_ID_LIST as CONST_LINE_ID_LIST
from utils.constants import NEVER_SKIP_LIST, POLYGON_FILE, PROCESSED_DIR
from utils.segment_ops import (
    calculate_linestring_length,
    combine_next_segment,
    combine_previous_segment,
    is_first_segment,
    is_last_segment,
    parse_geo_shape,
    remove_first_segment,
    remove_last_segment,
)

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.hasHandlers():
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(_h)


# ------------------------------------------------------------------------------
# Debug helper (optional)
# ------------------------------------------------------------------------------
def _print_all_segments(segment_df: pd.DataFrame) -> None:
    """Print a quick listing of segments (for ad-hoc debugging)."""
    logger.debug("Number of total segments: %d", len(segment_df))
    logger.debug("Columns: %s", list(segment_df.columns))
    for i in range(len(segment_df)):
        row = segment_df.iloc[i]
        logger.debug(
            "Segment #%d: %s - %s | length=%.2f",
            i + 1,
            row.get("START_OP"),
            row.get("END_OP"),
            row.get("polygon_length"),
        )


# ------------------------------------------------------------------------------
# Core decision for each segment
# ------------------------------------------------------------------------------
def choose_action(
    i: int, segment_df: pd.DataFrame, threshold: float, never_skip: List[str]
) -> Tuple[pd.DataFrame, int]:
    """
    Decide what to do with the current segment at index i:
      - Keep if long enough.
      - If short, try merging forward/backward, or remove when allowed.
      - Respect NEVER_SKIP_LIST stations to avoid removing critical endpoints.

    Returns:
      (possibly-updated DataFrame, next index to process)
    """
    row = segment_df.iloc[i]
    start = row["START_OP"]
    end = row["END_OP"]
    length = row["polygon_length"]

    # Keep long-enough segments
    if length >= threshold:
        return segment_df, i + 1

    # Handle short segments
    first = is_first_segment(i)
    last = is_last_segment(i, segment_df)

    # Case A: First segment (but not the only one)
    if first and not last:
        if end not in never_skip:
            # Merge forward
            return combine_next_segment(segment_df, i, logger)
        elif end in never_skip and start not in never_skip:
            # Drop first
            return remove_first_segment(segment_df), i

    # Case B: Middle segment
    if not first and not last:
        if end not in never_skip:
            # Merge forward
            return combine_next_segment(segment_df, i, logger)
        elif end in never_skip and start not in never_skip:
            # Merge backward
            return combine_previous_segment(segment_df, i, logger)

    # Case C: Last segment (but not the only one)
    if last and not first:
        if start not in never_skip:
            # Merge backward
            return combine_previous_segment(segment_df, i, logger)
        if start in never_skip and end not in never_skip:
            # Drop last
            return remove_last_segment(segment_df), i

    # Case D: Only segment in the line
    if first and last:
        if start not in never_skip and end not in never_skip:
            # Drop the only segment if both ends are not protected
            return remove_first_segment(segment_df), i
        else:
            # Keep protected singleton
            return segment_df, i + 1

    # Fallback: move on
    return segment_df, i + 1


# ------------------------------------------------------------------------------
# Stage 01 runner
# ------------------------------------------------------------------------------
def run(debug: bool = False) -> None:
    """
    Execute Stage 01:
      - Load + filter input
      - Parse geometry & compute metrics
      - Per-line short-segment cleanup
      - Save cleaned dataset
      - Run validations
    """
    # De-dup the line list, preserve as a stable iteration set
    LINE_ID_LIST = list(set(CONST_LINE_ID_LIST))

    logger.info("🚧 CLOSENESS_THRESHOLD: %.2f meters", CLOSENESS_THRESHOLD)
    logger.info("🚀 Stage 01 started: Clean and analyze line segment geometries")

    # Ensure output dir exists
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Load
    try:
        df = pd.read_csv(POLYGON_FILE, delimiter=";")
        logger.info("📥 Loaded: %s (%d rows)", POLYGON_FILE, len(df))
    except Exception as e:
        logger.error("❌ Failed to load %s: %s", POLYGON_FILE, e)
        return

    # Filter by LINE_ID_LIST
    df = df[df["Linie"].isin(LINE_ID_LIST)].copy()
    logger.info("🔎 Filtered by LINE_ID_LIST → %d rows remain", len(df))

    # Parse geometry and compute metrics
    df["_coordinates"] = df["Geo shape"].apply(parse_geo_shape)
    df["polygon_length"] = df["_coordinates"].apply(calculate_linestring_length)
    df["number_of_polygon_points"] = df["_coordinates"].apply(len)

    keep_cols = [
        "Linie",
        "START_OP",
        "END_OP",
        "KM START",
        "KM END",
        "polygon_length",
        "number_of_polygon_points",
        "Geo shape",
        "_coordinates",
    ]
    df = df[keep_cols].reset_index(drop=True)

    # Process per line (Linie)
    all_processed_dfs: List[pd.DataFrame] = []
    for idx, line_id in enumerate(LINE_ID_LIST, start=1):
        logger.info("📊 Line %d/%d — Linie=%s", idx, len(LINE_ID_LIST), line_id)
        segment_df = (
            df[df["Linie"] == line_id].sort_values("KM START").reset_index(drop=True)
        )

        # Walk through segments, merging/removing shorts
        i = 0
        while i < len(segment_df):
            segment_df, i = choose_action(
                i, segment_df, CLOSENESS_THRESHOLD, NEVER_SKIP_LIST
            )

        all_processed_dfs.append(segment_df)

    # Concatenate all lines back together
    final_df = pd.concat(all_processed_dfs, ignore_index=True)
    final_df.sort_values(by=["Linie", "KM START"], inplace=True)
    final_df.reset_index(drop=True, inplace=True)

    # Save
    final_df.to_csv(
        FILTERED_SUB_NETWORK_POLYGON_FILE, index=False, sep=";", encoding="utf-8-sig"
    )
    logger.info("✍️ Saved: %s", FILTERED_SUB_NETWORK_POLYGON_FILE.resolve())
    logger.info("🏁 Stage 01 cleaning complete. Total segments: %d", len(final_df))

    # --------------------------------------------------------------------------
    # Final validations
    # --------------------------------------------------------------------------
    logger.info("🔎 Final validations...")

    # 1) LINE_ID presence
    final_line_ids = set(final_df["Linie"].unique())
    missing_line_ids = set(LINE_ID_LIST) - final_line_ids
    extra_line_ids = final_line_ids - set(LINE_ID_LIST)

    if missing_line_ids:
        logger.warning("⚠️ Missing LINE_IDs in final output: %s", missing_line_ids)
    if extra_line_ids:
        logger.warning("⚠️ Extra LINE_IDs in final output: %s", extra_line_ids)
    logger.info("✅ LINE_ID validation done.")

    # 2) NEVER_SKIP_LIST presence
    all_ops = set(final_df["START_OP"]).union(final_df["END_OP"])
    missing_never_skip = set(NEVER_SKIP_LIST) - all_ops
    if missing_never_skip:
        logger.warning(
            "⚠️ NEVER_SKIP_LIST stations missing in final data: %s",
            missing_never_skip,
        )
    else:
        logger.info("✅ All NEVER_SKIP_LIST stations present.")

    # 3) No short segments should remain
    short_segments = final_df[final_df["polygon_length"] < CLOSENESS_THRESHOLD]
    if not short_segments.empty:
        logger.warning(
            "⚠️ Segments below threshold (%.2f m) still exist:", CLOSENESS_THRESHOLD
        )
        for _, r in short_segments.iterrows():
            logger.warning(
                "   %s - %s (%.2f m)", r["START_OP"], r["END_OP"], r["polygon_length"]
            )
    else:
        logger.info("✅ No segments below closeness threshold.")

    logger.info("🏁 Final validation completed.")
