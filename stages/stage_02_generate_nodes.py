import os
import json
import logging
import pandas as pd
from pathlib import Path
from shapely.geometry import LineString
import statistics
from utils.constants import (
    MAX_PLATFORM_COUNT, MIN_PLATFORM_COUNT, DEFAULT_PLATFORM_COUNT,
    MIN_PLATFORM_LENGTH, MAX_PLATFORM_LENGTH, DEFAULT_PLATFORM_LENGTH,
    PROCESSED_DIR, FILTERED_SUB_NETWORK_POLYGON_FILE, PLATFORM_LENGTH_DECISION_METHOD, FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH, FILL_EMPTY_PLATFORM_NO_DATA_WITH,PLATFORM_FILE
)


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

# ------------------------
# Main Stage 02
# ------------------------

def run():
    
    logger.info("\n🚀 Stage 02 started: Decide Platform Length for Sub-Network Stations")
    method = "N/A"
    if PLATFORM_LENGTH_DECISION_METHOD == "X":
        method = "Maximum platform length"
    elif PLATFORM_LENGTH_DECISION_METHOD == "N":
        method = "Minimum platform length"
    elif PLATFORM_LENGTH_DECISION_METHOD == "A":
        method = "Average platform length"
    elif PLATFORM_LENGTH_DECISION_METHOD == "D":
        method = "Default platform length"

    logger.info(f"\nSelected Decision Method is: {method} meters")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    try:
        platform_cols_to_read = ['Line','Station abbreviation', 'Customer track number','Platform number', 'Length of platform edge']
        polygon_df = pd.read_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, delimiter=';')
        perron_df = pd.read_csv(PLATFORM_FILE, delimiter=';', usecols=platform_cols_to_read)
        unique_ops = set(polygon_df["START_OP"]).union(polygon_df["END_OP"])
        perron_df = perron_df[perron_df['Station abbreviation'].isin(unique_ops)].copy()
        unique_perron_stations = set(perron_df["Station abbreviation"])
        
        
        logger.info(f"🔎 Filtered perronkante by Station abbreviation: {len(unique_perron_stations)} unique stations")
        logger.info(f"📥 Loaded sub_network polygon file: {FILTERED_SUB_NETWORK_POLYGON_FILE} ({len(unique_ops)} unique stations)")
    except Exception as e:
        logger.error(f"❌ Failed to load input CSV: {e}")
        return
    processed_rows = []
    for idx, op in enumerate(unique_ops, 1):
        logger.info(f"\n📊 Station id {str(idx)}/{len(unique_ops)} - Station Abbrv: {op}")
        current_station_perron_df = perron_df[perron_df['Station abbreviation'] == op].copy()
        platform_length = 0 
        platform_count = 0
        if current_station_perron_df.empty:
            
            if FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH == "X":
                platform_length = MAX_PLATFORM_LENGTH
            elif FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH == "N":
                platform_length = MIN_PLATFORM_LENGTH
            elif FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH == "D":
                platform_length = DEFAULT_PLATFORM_LENGTH
            if FILL_EMPTY_PLATFORM_NO_DATA_WITH == "X":
                platform_count = MAX_PLATFORM_COUNT
            elif FILL_EMPTY_PLATFORM_NO_DATA_WITH == "N":
                platform_count = MIN_PLATFORM_COUNT
            elif FILL_EMPTY_PLATFORM_NO_DATA_WITH == "D":
                platform_count = DEFAULT_PLATFORM_COUNT  
           
            result = {
                "station": op,
                "minimum_platform_length": platform_length,
                "maximum_platform_length": platform_length,
                "average_platform_length": platform_length,
                "platform_length": platform_length,
                "platform_count": platform_count
                }    
            processed_rows.append(result)
                
        
        else:
            unique_customer_tracks = set(current_station_perron_df['Platform number'].dropna().unique())
            current_station_info = []
            platform_count = len(unique_customer_tracks)
            for idy, track in enumerate(unique_customer_tracks, 1):
                current_track_df = current_station_perron_df[current_station_perron_df['Platform number'] == track].copy()
                track_length = current_track_df["Length of platform edge"].sum()
                current_station_info.append(track_length)

            # 🔐 Check if we got valid data
            if current_station_info:
                min_calculated_length = min(current_station_info)
                max_calculated_length = max(current_station_info)
                av_calculated_length = statistics.mean(current_station_info)

                if PLATFORM_LENGTH_DECISION_METHOD == "X":
                    platform_length = min(MAX_PLATFORM_LENGTH, max_calculated_length)
                elif PLATFORM_LENGTH_DECISION_METHOD == "N":
                    platform_length = max(MIN_PLATFORM_LENGTH, min_calculated_length)
                elif PLATFORM_LENGTH_DECISION_METHOD == "A":
                    platform_length = max(MIN_PLATFORM_LENGTH, min(MAX_PLATFORM_LENGTH, av_calculated_length))
                elif PLATFORM_LENGTH_DECISION_METHOD == "D":
                    platform_length = DEFAULT_PLATFORM_LENGTH

                if len(unique_customer_tracks) > MAX_PLATFORM_COUNT:
                    platform_count = MAX_PLATFORM_COUNT
                elif len(unique_customer_tracks) < MIN_PLATFORM_COUNT:
                    platform_count = MIN_PLATFORM_COUNT

                result = {
                    "station": op,
                    "minimum_platform_length": min_calculated_length,
                    "maximum_platform_length": max_calculated_length,
                    "average_platform_length": av_calculated_length,
                    "platform_length": platform_length,
                    "platform_count": platform_count
                }

                processed_rows.append(result)
            else:
                logger.warning(f"⚠️ Station {op} has no valid platform length info in customer tracks.")

            
    platform_df = pd.DataFrame(processed_rows)
    print(platform_df)
            
