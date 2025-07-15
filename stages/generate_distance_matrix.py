import pandas as pd
import numpy as np
import json
import ast
import logging
from pathlib import Path
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.constants import STATION_HELPER_FILE, PROCESSED_DIR

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(handler)

def euclidean_distance(coord1: list, coord2: list) -> float:
    """
    Calculate Euclidean distance between two coordinates.

    Args:
        coord1 (list): [X, Y] coordinate.
        coord2 (list): [X, Y] coordinate.

    Returns:
        float: Distance in same units as input (usually meters).
    """
    return np.sqrt((coord1[0] - coord2[0]) ** 2 + (coord1[1] - coord2[1]) ** 2)

def safe_eval(s: str) -> dict:
    """
    Safely evaluate a string representing a Python literal (like dict).

    Args:
        s (str): String to evaluate.

    Returns:
        dict: Parsed dictionary or empty dict on failure.
    """
    try:
        return ast.literal_eval(s)
    except Exception as e:
        logger.warning(f"⚠️ Failed to parse connected_stations: {s} → {e}")
        return {}

def generate_distance_matrices(threshold: float = 500.0) -> None:
    """
    Generate station-to-station distance matrices and flag close-but-unconnected pairs.

    Args:
        threshold (float, optional): Distance threshold in meters to flag unconnected close stations. Defaults to 500.0.
    """
    try:
        logger.info("🚀 Loading station helper data...")
        df = pd.read_csv(STATION_HELPER_FILE)

        # Parse center coordinates
        df['center_coordinates'] = df['center_coordinates'].apply(
            lambda x: json.loads(x.replace("'", '"')) if pd.notna(x) else None
        )

        # Prepare wide matrix
        stations = df['station'].tolist()
        wide_matrix = pd.DataFrame(index=stations, columns=stations, dtype=float)
        
        logger.info("📏 Calculating pairwise distances...")
        for i, row_i in df.iterrows():
            for j, row_j in df.iterrows():
                if row_i['station'] == row_j['station']:
                    dist = 0.0
                else:
                    dist = euclidean_distance(row_i['center_coordinates'], row_j['center_coordinates'])
                wide_matrix.at[row_i['station'], row_j['station']] = dist

        wide_matrix_path = PROCESSED_DIR / 'station_distance_matrix_wide.csv'
        wide_matrix.to_csv(wide_matrix_path)
        logger.info(f"✅ Saved wide matrix to: {wide_matrix_path}")

        # Prepare long matrix
        logger.info("📊 Preparing long matrix with connection info...")
        records = []
        for i, row_i in df.iterrows():
            connections_i = safe_eval(row_i['connected_stations'])
            for j, row_j in df.iterrows():
                if i >= j:
                    continue  # skip duplicates and self-pairs
                dist = wide_matrix.at[row_i['station'], row_j['station']]
                connected = (
                    row_j['station'] in connections_i.get('West', set())
                    or row_j['station'] in connections_i.get('East', set())
                )
                records.append({
                    'station_1': row_i['station'],
                    'station_2': row_j['station'],
                    'distance_m': dist,
                    'connected': connected
                })
        long_df = pd.DataFrame(records)
        long_matrix_path = PROCESSED_DIR / 'station_distance_matrix_long.csv'
        long_df.to_csv(long_matrix_path, index=False)
        logger.info(f"✅ Saved long matrix to: {long_matrix_path}")

        # Flag close but unconnected
        logger.info(f"⚠️ Flagging pairs under {threshold} m without connection...")
        close_unconnected = long_df[(long_df['distance_m'] < threshold) & (~long_df['connected'])]
        close_unconnected_path = PROCESSED_DIR / 'close_unconnected_stations.csv'
        close_unconnected.to_csv(close_unconnected_path, index=False)
        logger.info(f"⚠️ Saved close-but-unconnected stations to: {close_unconnected_path}")

    except Exception as e:
        logger.error(f"❌ Failed to generate distance matrices: {e}")
        raise

if __name__ == "__main__":
    generate_distance_matrices()
