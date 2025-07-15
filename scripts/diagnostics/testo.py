
import os
import json
import logging
import pandas as pd
from pathlib import Path
from shapely.geometry import LineString

LINE_ID = 710
RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
PLATFORM_FILE = RAW_DIR / "perronkante.csv"
FILTERED_SUB_NETWORK_POLYGON_FILE = PROCESSED_DIR / "filtered_sub_network_data.csv"
OUTPUT_PLATFORM_FILE = PROCESSED_DIR / "station_platform_info.csv"
POLYGON_FILE = RAW_DIR / "linie_mit_polygon.csv"
filtered_df = pd.read_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, delimiter=';')
filtered_df = filtered_df[filtered_df['Linie']==LINE_ID].copy()
sorted_filtered_df = filtered_df[filtered_df["Linie"] == LINE_ID].sort_values("KM START").reset_index(drop=True)

original_df = pd.read_csv(POLYGON_FILE, delimiter=';')
original_df = original_df[original_df['Linie']==LINE_ID].copy()
sorted_original_df = original_df[original_df["Linie"] == LINE_ID].sort_values("KM START").reset_index(drop=True)


def print_all_segments(segment_df: pd.DataFrame):
    print(f"Number of Total segments found: {len(segment_df)}")
    #print(segment_df.columns)
    for i in range(len(segment_df)):
        row = segment_df.iloc[i]
        print(f"Segment no: {i+1}   {row['START_OP']} - {row['END_OP']} {row['polygon_length']}")

print("\n ================= Original Segment Info ===================")

print_all_segments(sorted_original_df)
print("\n ================= Original Segment Info ===================")

print("\n ================= Filtered Segment Info ===================")
print_all_segments(sorted_filtered_df)
print("\n ================= Filtered Segment Info ===================")


