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
from utils.constants import (CLOSENESS_THRESHOLD, PROCESSED_DIR, POLYGON_FILE, FILTERED_SUB_NETWORK_POLYGON_FILE, LINE_ID_LIST as CONST_LINE_ID_LIST, NEVER_SKIP_LIST)

# ------------------------
# Logging setup
# ------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
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
def choose_action(i, segment_df: pd.DataFrame, threshold: int, never_skip: list):
    row = segment_df.iloc[i]
    start, end, length = row['START_OP'], row['END_OP'], row['polygon_length']
    #logger.info(f"\n🧩 Processing segment {start} - {end} (index {i})")
    
    #if the segment is long enough
    if length >= threshold:
        #logger.info(f"✅ Segment: {start} - {end} is long enough. Keeping it.")
        return segment_df, i + 1

    #if the segment is SHORT
    else:
        #logger.info("👷 Segment is SHORT.")
        first = is_first_segment(i)
        last = is_last_segment(i, segment_df)
        if first and not last: #IF THE SEGMENT IS FIRST SEGMENT AND NOT THE ONLY SEGMENT
            if end not in never_skip:
                #logger.debug("🗑️ First segment → combine_next_segment.")
                return combine_next_segment(segment_df, i, logger)
            elif end in never_skip and start not in never_skip:
                #logger.debug("🗑️ First segment → remove_first_segment.")
                return remove_first_segment(segment_df), i

        if not first and not last: #IF THE SEGMENT IS MID SEGMENT 
            
            if end not in never_skip:
                #logger.debug("🗑️ Mid segment → combine_next_segment.")
                return combine_next_segment(segment_df, i, logger)
            elif end in never_skip and start not in never_skip:
                #logger.debug("🗑️ Mid segment → combine_previous_segment.")
                return combine_previous_segment(segment_df, i, logger)

        if last and not first: #IF THE SEGMENT IS LAST SEGMENT
            if start not in never_skip:
                #logger.debug("🗑️ Last segment → combine_previous_segment.")
                return combine_previous_segment(segment_df, i, logger)
            if start in never_skip and end not in never_skip:
                #logger.debug("🗑️ Last segment → remove_last_segment.")
                return remove_last_segment(segment_df), i

        if first and last: #IF THE SEGMENT IS THE ONLY SEGMENT
            if start not in never_skip and end not in never_skip:
                #logger.debug("🗑️ ONLY segment → remove_first_segment.")
                return remove_first_segment(segment_df), i
            else:
                #logger.debug("⚠️ Only segment but in NEVER_SKIP_LIST → keeping it.")
                return segment_df, i + 1

    return segment_df, i + 1

def run(debug=False):
    LINE_ID_LIST = list(set(CONST_LINE_ID_LIST))
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
        #print_all_segments(segment_df)

        i = 0
        while i < len(segment_df):
            segment_df, i = choose_action(i, segment_df, CLOSENESS_THRESHOLD, NEVER_SKIP_LIST)

        all_processed_dfs.append(segment_df)
        print(f"all_processed_dfs length: {str(len(all_processed_dfs))}")
    duplicates = df[df.duplicated(subset=['Linie', 'START_OP', 'END_OP', 'KM START', 'KM END'], keep=False)]


    
    print(f"\n⚠️ Found {len(duplicates)} duplicate rows BEFORE final_df (counting all occurrences):")
    final_df = pd.concat(all_processed_dfs, ignore_index=True)
    duplicates_final = final_df[final_df.duplicated(subset=['Linie', 'START_OP', 'END_OP', 'KM START', 'KM END'], keep=False)]


    if not duplicates_final.empty:
        print(f"\n⚠️ Found {len(duplicates_final)} duplicate rows AFTER final_df (counting all occurrences):")
    final_df.to_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, index=False, sep=';', encoding='utf-8-sig')
    logger.info(f"\n✍️ Combined file saved at: {FILTERED_SUB_NETWORK_POLYGON_FILE.resolve()}")
    logger.info(f"🏁 Stage 01 segment cleaning completed. Total segments: {len(final_df)}")

    # ------------------------
    # ✅ Final Validation Layer
    # ------------------------
    logger.info("\n🔎 Performing final validations...")

    # 1️⃣ LINE_ID validation
    final_line_ids = set(final_df['Linie'].unique())
    missing_line_ids = set(LINE_ID_LIST) - final_line_ids
    extra_line_ids = final_line_ids - set(LINE_ID_LIST)

    if missing_line_ids:
        logger.warning(f"⚠️ Missing LINE_IDs in final output: {missing_line_ids}")
    if extra_line_ids:
        logger.warning(f"⚠️ Extra LINE_IDs in final output (unexpected): {extra_line_ids}")
    logger.info("✅ LINE_ID validation complete.")

    # 2️⃣ NEVER_SKIP_LIST validation
    all_ops = set(final_df['START_OP']).union(final_df['END_OP'])
    missing_never_skip = set(NEVER_SKIP_LIST) - all_ops
    if missing_never_skip:
        logger.warning(f"⚠️ NEVER_SKIP_LIST stations missing in final data: {missing_never_skip}")
    else:
        logger.info("✅ All NEVER_SKIP_LIST stations present.")

    # 3️⃣ Polygon length validation
    short_segments = final_df[final_df['polygon_length'] < CLOSENESS_THRESHOLD]
    if not short_segments.empty:
        logger.warning(f"⚠️ Segments below closeness threshold ({CLOSENESS_THRESHOLD} m):")
        for _, row in short_segments.iterrows():
            logger.warning(f"   {row['START_OP']} - {row['END_OP']} ({row['polygon_length']} m)")
    else:
        logger.info("✅ No segments below closeness threshold.")

    logger.info("🏁 Final validation completed.")
