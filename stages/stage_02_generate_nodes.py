import pandas as pd
import logging
from pathlib import Path
from utils.constants import (
    PROCESSED_DIR, FILTERED_SUB_NETWORK_POLYGON_FILE, PLATFORM_FILE, STATION_HELPER_FILE, NEVER_SKIP_LIST
)
from utils.platform_ops import (
    filter_perron_data, build_station_info, find_station_connections, define_station_types, find_entry_nodes
)

def setup_logger(debug_mode=False):
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    return logger

def run(debug=False):
    logger = setup_logger(debug)
    logger.info("🚀 Stage 02 started: Generate station info")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Load data
        polygon_df = pd.read_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, delimiter=';')
        perron_df = pd.read_csv(PLATFORM_FILE, delimiter=';')

        # Filter perron data to only include used stations
        unique_ops = set(polygon_df['START_OP']).union(polygon_df['END_OP'])
        perron_df_filtered = filter_perron_data(perron_df, unique_ops)

        logger.info(f"🔎 Found {len(unique_ops)} unique stations in polygon file")
        logger.info(f"🔎 Filtered perronkante: {len(perron_df_filtered)} rows")

        # Build station info
        station_info_df = build_station_info(polygon_df, perron_df_filtered, logger)

        # Add connected stations
        station_info_df = find_station_connections(station_info_df, polygon_df, logger)

        # Define station types
        station_info_df = define_station_types(station_info_df)
        
        # Find Entry Nodes
        station_info_df = find_entry_nodes(station_info_df, polygon_df, logger)

        # Save station info CSV
        station_info_df.sort_values(by='station', inplace=True)
        station_info_df.to_csv(STATION_HELPER_FILE, index=False, sep=';', encoding='utf-8-sig')
        logger.info(f"✅ Saved station info CSV to: {STATION_HELPER_FILE.resolve()}")

    except Exception as e:
        logger.error(f"❌ Stage 02 failed: {e}")
    # ------------------------
    # ✅ Final Validation Layer
    # ------------------------
    logger.info("\n🔎 Performing final validations...")
    # 1️⃣ Number of stations validation
    polygon_unique_stations = set(polygon_df['START_OP']).union(polygon_df['END_OP'])
    platform_unique_stations = set(station_info_df['station'])
    if len(polygon_unique_stations) != len(platform_unique_stations):
        logger.warning(f"⚠️ 1️⃣ Number of stations validation FAILED")
    else:
        logger.info("✅ Number of stations validation PASSED")
    # 2️⃣ NEVER SKIP LIST VALIDATION
    missing_never_skip = set(NEVER_SKIP_LIST) - polygon_unique_stations
    if missing_never_skip:
        logger.warning(f"⚠️ NEVER_SKIP_LIST stations missing in final data: {missing_never_skip}")
    else:
        logger.info("✅ All NEVER_SKIP_LIST stations present.")
    # 3️⃣ ISOLATED STATION VALIDATION
    isolated_stations = set(station_info_df[station_info_df['type'] == 'isolated']['station'])
    if len(isolated_stations)>0:

        logger.warning(f"⚠️ ISOLATED STATION VALIDATION FAILED... There are total : {len(isolated_stations)} isolated ")
        print("\t ===========LIST OF ISOLATED STATIONS=========")
        for idx, row in isolated_stations:
            print(f"\t \t No {idx+1}: {row['station']}")
    else:
        logger.info("✅ ISOLATED STATION VALIDATION PASSED")       
    
    logger.info("✅ STAGE 02 VALIDATION complete.")