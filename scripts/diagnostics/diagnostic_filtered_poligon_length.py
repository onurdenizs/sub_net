"""
Diagnostic script for inspecting segment polygon lengths in filtered_sub_network_data.csv

✅ Forces polygon_length to float
✅ Handles string/numeric conversion issues, NaNs
✅ Logs and prints segments shorter than threshold
✅ Lists top 10 shortest and longest segments properly
✅ Designed for Windows local execution
"""

import pandas as pd
import numpy as np
import logging
import os

# === CONFIG ===
CSV_PATH = r"D:\PhD\dec2025\data\processed\filtered_sub_network_data.csv"
SHORTNESS_THRESHOLD = 1000  # meters
LOG_LEVEL = logging.INFO

# === Setup Logging ===
logging.basicConfig(level=LOG_LEVEL, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_data(filepath):
    """
    Loads CSV and safely converts polygon_length to float
    Returns a cleaned DataFrame
    """
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        raise FileNotFoundError(f"File not found: {filepath}")

    df = pd.read_csv(filepath)

    if "polygon_length" not in df.columns:
        logger.error("Missing 'polygon_length' column in input CSV")
        raise ValueError("Missing 'polygon_length' column")

    # Clean polygon_length to ensure it's numeric
    df["polygon_length"] = pd.to_numeric(df["polygon_length"], errors="coerce")

    # Drop rows with missing START_OP or END_OP just in case
    df = df.dropna(subset=["START_OP", "END_OP", "polygon_length"])

    return df

def print_header(title):
    print("\n" + "="*80)
    print(f"{title.center(80)}")
    print("="*80)

def main():
    df = load_data(CSV_PATH)

    # Handle NaNs after conversion
    nan_rows = df[df["polygon_length"].isna()]
    if not nan_rows.empty:
        logger.warning(f"{len(nan_rows)} rows have NaN polygon_length after conversion")
        print(nan_rows[["START_OP", "END_OP", "polygon_length"]])

    # Sort properly
    df_sorted = df.sort_values(by="polygon_length", ascending=True)

    # Top 10 shortest
    print_header("🔻 10 Shortest Segments by Polygon Length")
    print(df_sorted[["START_OP", "END_OP", "polygon_length"]].head(10).to_string(index=False))

    # Top 10 longest
    print_header("🔺 10 Longest Segments by Polygon Length")
    print(df_sorted[["START_OP", "END_OP", "polygon_length"]].tail(10).to_string(index=False))

    # Segments below threshold
    short_segments = df_sorted[df_sorted["polygon_length"] < SHORTNESS_THRESHOLD]

    print_header(f"⚠️ Segments shorter than {SHORTNESS_THRESHOLD} meters")
    print(short_segments[["START_OP", "END_OP", "polygon_length"]].to_string(index=False))
    print(f"\nTotal short segments found: {len(short_segments)}")

    # Optional: export for debugging
    debug_path = os.path.join(os.path.dirname(CSV_PATH), "diagnostic_short_segments.csv")
    short_segments.to_csv(debug_path, index=False)
    logger.info(f"Diagnostic file saved: {debug_path}")

if __name__ == "__main__":
    main()
