"""
Stage 01 - Clean Stations
--------------------------
This stage filters and preprocesses the raw polygon and platform data
for a selected subset of railway lines in the Swiss rail network simulation project.

It reads two CSV files:
    - linie_mit_polygon.csv: raw segment geometries and station pairs
    - perronkante.csv: platform edge lengths, types, and station mappings

Only selected line IDs are retained for further modeling.
Additional constants are declared to configure downstream geometry generation.

Author: Onur Deniz
"""

import os
import logging
import pandas as pd

# ============================================================================
# 🚦 STAGE CONSTANTS
# ============================================================================

# Key stations that must never be skipped regardless of thresholds
NEVER_SKIP_LIST = ['LZ', 'BS', 'BN', 'ZUE', 'LS', 'GE']

# Platform geometry parameters (in meters)
MIN_PLATFORM_LENGTH = 350
MAX_PLATFORM_LENGTH = 750
DEFAULT_PLATFORM_LENGTH = 400

# Entry offset values (in meters)
ENTRY_OFFSET_BUFFER = 350
MIN_ENTRY_OFFSET = 200
CONSTANT_ENTRY_OFFSET = 300

# Platform count thresholds
MAX_PLATFORM_COUNT = 20
DEFAULT_PLATFORM_COUNT = 2

# Minimum length of a main line to consider as a valid operational segment
MIN_MAIN_LINE_LENGTH = 300

# Entry offset method: 'H' = Half, 'M' = Mean, 'C' = Constant
ENTRY_OFFSET_METHOD = "M"

# Line IDs of interest (used for filtering the dataset)
LINE_ID_LIST = [
    850, 751, 710, 650, 540, 450, 250, 100, 501, 500,
    722, 723, 720, 890, 900, 150, 200, 210, 410, 250, 400, 452
]

# ============================================================================
# 🔧 Logging setup
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================================
# 🚀 Main run function
# ============================================================================

def run():
    """Main function to execute Stage 01 - Clean Stations."""
    try:
        logger.info("📥 Reading raw datasets...")

        base_path = "D:/PhD/dec2025/data/raw"
        polygon_path = os.path.join(base_path, "linie_mit_polygon.csv")
        perronkante_path = os.path.join(base_path, "perronkante.csv")

        polygon_df = pd.read_csv(polygon_path, sep=";", dtype=str)
        perronkante_df = pd.read_csv(perronkante_path, sep=";", dtype=str)

        logger.info(f"✅ Read linie_mit_polygon.csv with {len(polygon_df)} rows.")
        logger.info(f"✅ Read perronkante.csv with {len(perronkante_df)} rows.")

        # Convert relevant fields to numeric where applicable
        polygon_df["Linie"] = pd.to_numeric(polygon_df["Linie"], errors="coerce")
        perronkante_df["Length of platform edge"] = pd.to_numeric(
            perronkante_df["Length of platform edge"], errors="coerce"
        )

        # Apply filtering
        filtered_polygon_df = polygon_df[polygon_df["Linie"].isin(LINE_ID_LIST)]
        logger.info(
            f"🔎 Filtered polygon data: {len(filtered_polygon_df)} rows remain after applying LINE_ID_LIST."
        )

        logger.info(f"🛠️ ENTRY_OFFSET_METHOD set to '{ENTRY_OFFSET_METHOD}' with buffer {ENTRY_OFFSET_BUFFER} m")

        logger.info("📦 Stage 01 completed.")

    except Exception as e:
        logger.error(f"❌ Stage 01 failed: {e}")
        raise
