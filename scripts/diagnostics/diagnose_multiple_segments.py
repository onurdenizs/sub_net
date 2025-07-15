
import os
import json
import logging
import pandas as pd
from pathlib import Path
from shapely.geometry import LineString


LINE_ID_LIST = [850, 751, 710, 650, 540, 450, 250, 100, 501, 500,
                722, 723, 720, 890, 900, 150, 200, 210, 410, 250, 400, 452, 451]
NEVER_SKIP_LIST = ['LZ', 'BS', 'BN', 'ZUE', 'LS', 'GE'] #, 'ABOW', 'ABO', 'RTR'
MIN_PLATFORM_LENGTH = 200         # meters
MAX_PLATFORM_LENGTH = 500         # meters
DEFAULT_PLATFORM_LENGTH = 250     # meters
ENTRY_OFFSET_BUFFER = 300         # meters
MIN_MAIN_LINE_LENGTH = 400        # meters
MAX_PLATFORM_COUNT = 20           # meters
MIN_PLATFORM_COUNT = 2            # meters
DEFAULT_PLATFORM_COUNT = 5        # meters
DEFAULT_PLATFORM_OFFSET = 2       # meters
CLOSENESS_THRESHOLD = (
    MAX_PLATFORM_LENGTH + ENTRY_OFFSET_BUFFER * 2 + MIN_MAIN_LINE_LENGTH
)


PLATFORM_LENGTH_DECISION_METHOD = "X" #X: maximum platform length, N: for minimum platform length, A: Average platform length D: Default platform length
FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH = "N" #D:default platform length, N: Minimum platform length, X: Maximum platform length 
FILL_EMPTY_PLATFORM_NO_DATA_WITH = "N" #D:default platform count, N: Minimum platform count, X: Maximum platform count


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
POLYGON_FILE = RAW_DIR / "linie_mit_polygon.csv"
FILTERED_SUB_NETWORK_POLYGON_FILE = PROCESSED_DIR / "filtered_sub_network_data.csv"
STATION_INFO_FILE = PROCESSED_DIR / "station_platform_info.csv"
PLATFORM_FILE = RAW_DIR / "perronkante.csv"
STATION_HELPER_FILE = PROCESSED_DIR / "station_info_master.csv"
STATION_ENTRY_NODE_FILE = PROCESSED_DIR / "station_entry_nodes.json"


polygon_df = pd.read_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, delimiter=';')
original_polygon_df = pd.read_csv(POLYGON_FILE, delimiter=';')
station_df = pd.read_csv(STATION_HELPER_FILE, delimiter=';')

# Koşullar
sta1 = "AVRY"
sta2 = "VG"

# 1️⃣ sta1 → sta2 yönündeki satırlar
forward_filtered = polygon_df[(polygon_df['START_OP'] == sta1) & (polygon_df['END_OP'] == sta2)]

# 2️⃣ sta2 → sta1 yönündeki satırlar
backward_filtered = polygon_df[(polygon_df['START_OP'] == sta2) & (polygon_df['END_OP'] == sta1)]
duplicates = polygon_df[polygon_df.duplicated()]
if len(duplicates)>0:
    print(f"Now duplicate row number is: {str(len(duplicates))}")
# Sonuçları raporla
print("\t =========FILTERED AND MERGED POLYGON DATA ============")
print(f"➡️ {sta1} → {sta2} count: {len(forward_filtered)}")
if not forward_filtered.empty:
    print(forward_filtered[['Linie', 'polygon_length']].to_string(index=False))

print(f"\n⬅️ {sta2} → {sta1} count: {len(backward_filtered)}")
if not backward_filtered.empty:
    print(backward_filtered[['Linie', 'polygon_length']].to_string(index=False))

# 1️⃣ sta1 → sta2 yönündeki satırlar
forward_original = original_polygon_df[(original_polygon_df['START_OP'] == sta1) & (original_polygon_df['END_OP'] == sta2)]

# 2️⃣ sta2 → sta1 yönündeki satırlar
backward_original = original_polygon_df[(original_polygon_df['START_OP'] == sta2) & (original_polygon_df['END_OP'] == sta1)]

# Sonuçları raporla
print("\t =========OORIGINAL POLYGON DATA ============")
print(f"➡️ {sta1} → {sta2} count: {len(forward_original)}")
if not forward_original.empty:
    print(forward_original[['Linie']].to_string(index=False))

print(f"\n⬅️ {sta2} → {sta1} count: {len(backward_original)}")
if not backward_original.empty:
    print(backward_original[['Linie']].to_string(index=False))
# Tüm kolonlara göre duplicate
duplicates = original_polygon_df[original_polygon_df.duplicated(keep=False)]

if not duplicates.empty:
    print(f"\n⚠️ Found {len(duplicates)} duplicate rows (counting all occurrences):")
    
    # Gruplayarak detaylı göster
    grouped = duplicates.groupby(['START_OP', 'END_OP'])
    for (start, end), group in grouped:
        print(f"\n➡️ {start} → {end} (count: {len(group)})")
        print(group[['Linie', 'KM START', 'KM END']])
else:
    print("✅ No duplicate rows found in the dataset!")

