import pandas as pd
import logging
from pathlib import Path
from utils.constants import (
    PROCESSED_DIR, FILTERED_SUB_NETWORK_POLYGON_FILE, PLATFORM_FILE, STATION_HELPER_FILE
)
from utils.platform_ops import (
    filter_perron_data, process_station_platform_info, find_station_connections, define_station_types
)

def setup_logger(debug_mode=False):
    """
    Setup logger with INFO or DEBUG level.

    Args:
        debug_mode (bool): Whether to enable debug mode.

    Returns:
        logging.Logger: Configured logger.
    """
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    return logger

def run(debug=False):
    """
    Stage 02: Decide Platform Length for Sub-Network Stations.

    Args:
        debug (bool): Enable debug logging.
    """
    logger = setup_logger(debug)
    logger.info("🚀 Stage 02 started: Decide Platform Length for Sub-Network Stations")

    # Ensure processed directory exists
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # 1️⃣ Load raw data
        platform_cols_to_read = [
            'Line', 'Station abbreviation', 'Customer track number',
            'Platform number', 'Length of platform edge'
        ]
        polygon_df = pd.read_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, delimiter=';')
        perron_df = pd.read_csv(PLATFORM_FILE, delimiter=';', usecols=platform_cols_to_read)

        # 2️⃣ Prepare unique stations
        unique_ops = set(polygon_df["START_OP"]).union(polygon_df["END_OP"])

        # 3️⃣ Filter perron data
        perron_df_filtered = filter_perron_data(perron_df, unique_ops)

        logger.info(f"🔎 Filtered perronkante by Station abbreviation: {len(set(perron_df_filtered['Station abbreviation']))} unique stations")
        logger.info(f"📥 Loaded sub_network polygon file: {FILTERED_SUB_NETWORK_POLYGON_FILE} ({len(unique_ops)} unique stations)")

        # 4️⃣ Process platform information
        platform_df = process_station_platform_info(perron_df_filtered, unique_ops, logger)
        platform_df = find_station_connections(platform_df)
        platform_df = define_station_types(platform_df)
        
        # 5️⃣ Save result
        
        platform_df.to_csv(STATION_HELPER_FILE, index=False, encoding='utf-8-sig')
        logger.info(f"✅ Saved platform info to: {STATION_HELPER_FILE.resolve()}")

    except Exception as e:
        logger.error(f"❌ Stage 02 failed: {e}")
        return
