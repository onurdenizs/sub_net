
import os
import json
import logging
import pandas as pd
from pathlib import Path
from shapely.geometry import LineString


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
PLATFORM_FILE = RAW_DIR / "perronkante.csv"
FILTERED_SUB_NETWORK_POLYGON_FILE = PROCESSED_DIR / "filtered_sub_network_data.csv"
OUTPUT_PLATFORM_FILE = PROCESSED_DIR / "station_platform_info.csv"
platform_cols_to_read = ['Line','Station abbreviation', 'Platform number', 'Customer track number','Length of platform edge']
perron_df = pd.read_csv(PLATFORM_FILE, delimiter=';', usecols=platform_cols_to_read)
op = 'ZUE'
current_station_perron_df = perron_df[perron_df['Station abbreviation'] == op].copy()
unique_customer_tracks = set(current_station_perron_df["Customer track number"].dropna().unique())
print(unique_customer_tracks)

print(f"unique track id count : {str(len(unique_customer_tracks))}")

for idx, track in enumerate(unique_customer_tracks, 1):
    current_track_df = current_station_perron_df[current_station_perron_df['Customer track number'] == track].copy()
    track_length = current_track_df["Length of platform edge"].sum()
    current_station_info = []
    result = {
                "station": op,
                "platform_no": track,
                "platform_length": track_length
                }   
    current_station_info.append(result) 
    print(current_station_info)