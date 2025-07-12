import os
import json
import logging
import pandas as pd
from pathlib import Path
from shapely.geometry import LineString
from utils.segment_ops import (
    parse_geo_shape,
    calculate_linestring_length,
    merge_geo_shapes,
    is_first_segment,
    is_last_segment,
    combine_next_segment,
    combine_previous_segment,
    remove_first_segment,
    remove_last_segment
)
from utils.constants import (CLOSENESS_THRESHOLD, PROCESSED_DIR, POLYGON_FILE, FILTERED_SUB_NETWORK_POLYGON_FILE, LINE_ID_LIST, NEVER_SKIP_LIST)

# ------------------------
# Logging setup
# ------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ------------------------
# Utility Functions
# ------------------------
def print_all_segments(segment_df: pd.DataFrame):
    print(f"Number of Total segments found: {len(segment_df)}")
    print(segment_df.columns)
    for i in range(len(segment_df)):
        row = segment_df.iloc[i]
        print(f"Segment no: {i+1}   {row['START_OP']} - {row['END_OP']} {row['polygon_length']}")

# ------------------------
# Main Stage 01
# ------------------------
def choose_action(i, segment_df, threshold, never_skip):
    row = segment_df.iloc[i]
    start, end, length = row['START_OP'], row['END_OP'], row['polygon_length']
    logger.info(f"\n🧩 Processing segment {start} - {end} (index {i})")

    if length >= threshold:
        logger.info("✅ Segment is long enough. Keeping it.")
        return segment_df, i + 1

    first = is_first_segment(i)
    last = is_last_segment(i, segment_df)

    logger.info(f"🔍 {'First' if first else ('Last' if last else 'Middle')} segment under threshold. Attempting actions...")

    if first and not last:
        if end not in never_skip:
            return combine_next_segment(segment_df, i)
        if end in never_skip and start not in never_skip:
            return remove_first_segment(segment_df), i

    if not first and not last:
        next_seg = segment_df.iloc[i + 1]
        prev_seg = segment_df.iloc[i - 1]
        if all(op not in never_skip for op in [start, end, next_seg['START_OP'], next_seg['END_OP']]):
            return combine_next_segment(segment_df, i)
        if end in never_skip and prev_seg['END_OP'] not in never_skip:
            return combine_previous_segment(segment_df, i)

    if last and not first:
        if start not in never_skip:
            return combine_previous_segment(segment_df, i)
        if start in never_skip and end not in never_skip:
            return remove_last_segment(segment_df), i

    return segment_df, i + 1

def run():
    logger.info(f"\n🚧 CLOSENESS_THRESHOLD calculated as: {CLOSENESS_THRESHOLD} meters")
    logger.info("\n🚀 Stage 01 started: Clean and analyze line segment geometries")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    try:
        df = pd.read_csv(POLYGON_FILE, delimiter=';')
        logger.info(f"📥 Loaded input file: {POLYGON_FILE} ({len(df)} rows)")
    except Exception as e:
        logger.error(f"❌ Failed to load input CSV: {e}")
        return

    df = df[df['Linie'].isin(LINE_ID_LIST)].copy()
    logger.info(f"🔎 Filtered by LINE_ID_LIST: {len(df)} rows remain")

    df['_coordinates'] = df['Geo shape'].apply(parse_geo_shape)
    df['polygon_length'] = df['_coordinates'].apply(calculate_linestring_length)
    df['number_of_polygon_points'] = df['_coordinates'].apply(lambda x: len(x))

    keep_cols = [
        "Linie", "START_OP", "END_OP", "KM START", "KM END",
        "polygon_length", "number_of_polygon_points", "Geo shape", "_coordinates"
    ]
    df = df[keep_cols].reset_index(drop=True)

    all_processed_dfs = []

    for idx, line_id in enumerate(LINE_ID_LIST, 1):
        logger.info(f"\n📊 Line {idx}/{len(LINE_ID_LIST)} - Linie {line_id}")
        segment_df = df[df["Linie"] == line_id].sort_values("KM START").reset_index(drop=True)
        print_all_segments(segment_df)

        i = 0
        while i < len(segment_df):
            segment_df, i = choose_action(i, segment_df, CLOSENESS_THRESHOLD, NEVER_SKIP_LIST)

        print_all_segments(segment_df)
        all_processed_dfs.append(segment_df)

        # ------------------------
        # ✅ Validation Layer
        # ------------------------
        logger.info("\n🔎 Performing final validations...")
        initial_segment_count = len(df[df['Linie'] == line_id])
        final_segment_count = len(segment_df)
        removed_or_combined_count = initial_segment_count - final_segment_count

        errors_found = False

        for idx2, row in segment_df.iterrows():
            if row["polygon_length"] < CLOSENESS_THRESHOLD:
                logger.warning(f"⚠️ Segment {row['START_OP']} - {row['END_OP']} is below closeness threshold: {row['polygon_length']} m")
                errors_found = True

            if row["number_of_polygon_points"] < 2:
                logger.warning(f"⚠️ Segment {row['START_OP']} - {row['END_OP']} has less than 2 polygon points.")
                errors_found = True

            if row["START_OP"] == row["END_OP"]:
                logger.warning(f"⚠️ Segment has identical START_OP and END_OP: {row['START_OP']}")
                errors_found = True

            try:
                parsed = parse_geo_shape(row["Geo shape"])
                if not parsed or not isinstance(parsed, list):
                    raise ValueError("Invalid parsed geometry")
            except Exception as e:
                logger.warning(f"⚠️ Failed to parse Geo shape for segment {row['START_OP']} - {row['END_OP']}: {e}")
                errors_found = True

        logger.info(f"Initial segment count: {initial_segment_count}")
        logger.info(f"Final segment count: {final_segment_count}")
        logger.info(f"Total segments removed/combined: {removed_or_combined_count}")

        if not errors_found:
            logger.info("✅ Validation passed. All segments meet the expected criteria.")
        else:
            logger.warning("❌ Validation failed. See warnings above.")

    final_df = pd.concat(all_processed_dfs, ignore_index=True)
    final_df.to_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, index=False, sep=';', encoding='utf-8-sig')
    logger.info(f"\n✍️ Combined file saved at: {FILTERED_SUB_NETWORK_POLYGON_FILE.resolve()}")
    logger.info(f"🏁 Stage 01 completed successfully. Total segments: {len(final_df)}")