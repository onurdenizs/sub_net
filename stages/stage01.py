import os
import json
import logging
import pandas as pd
from pathlib import Path
from shapely.geometry import LineString

# ------------------------
# Configuration
# ------------------------
RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
POLYGON_FILE = RAW_DIR / "linie_mit_polygon.csv"
OUTPUT_POLYGON_FILE = PROCESSED_DIR / "filtered_sub_network_data.csv"
REMOVED_SEGMENTS_FILE = PROCESSED_DIR / "removed_segments.csv"
REMOVED_STATIONS_FILE = PROCESSED_DIR / "removed_stations.txt"

LINE_ID_LIST = [710]

NEVER_SKIP_LIST = ['LZ', 'BS', 'BN', 'ZUE', 'LS', 'GE']
MIN_PLATFORM_LENGTH = 220         # meters
MAX_PLATFORM_LENGTH = 750         # meters
DEFAULT_PLATFORM_LENGTH = 350     # meters
ENTRY_OFFSET_BUFFER = 150         # meters
MIN_MAIN_LINE_LENGTH = 400        # meters
MAX_PLATFORM_COUNT = 20           # meters
DEFAULT_PLATFORM_COUNT = 2        # meters
CLOSENESS_THRESHOLD = (
    DEFAULT_PLATFORM_LENGTH + ENTRY_OFFSET_BUFFER * 2 + MIN_MAIN_LINE_LENGTH
)
removed_stations = set()
removed_segments = []
cleaned_segments = []

print("\n🚧 Calculated CLOSENESS_THRESHOLD:", CLOSENESS_THRESHOLD, "meters")

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
# Helper Functions
# ------------------------
def merge_geo_shapes(geo_1: str, geo_2: str) -> dict:
    """
    Merges two LineString GeoJSONs by concatenating their coordinates,
    skipping the first coordinate of geo_2 (because it's shared).
    
    Args:
        geo_1 (str or dict): Geo shape of first row
        geo_2 (str or dict): Geo shape of second row

    Returns:
        dict: Combined GeoJSON LineString
    """
    try:
        # Eğer string formatındaysa, parse et
        if isinstance(geo_1, str):
            geo_1 = json.loads(geo_1)
        if isinstance(geo_2, str):
            geo_2 = json.loads(geo_2)

        coords_1 = geo_1.get("coordinates", [])
        coords_2 = geo_2.get("coordinates", [])

        # Combine coordinates: coords_1 + coords_2 (ilk eleman hariç)
        combined_coords = coords_1 + coords_2[1:]

        return {
            "type": "LineString",
            "coordinates": combined_coords
        }

    except Exception as e:
        print(f"Geo shape merge error: {e}")
        return {
            "type": "LineString",
            "coordinates": []
        }
def print_all_segments(segment_df: pd.DataFrame ):
    print(f"Number of Total segments found: {str(len(segment_df))}")
    print(print(segment_df.columns))
    for i in range(0,len(segment_df)):
        current_segment = segment_df.iloc[[i]]
        current_START_OP = current_segment["START_OP"].values[0]
        current_END_OP = current_segment["END_OP"].values[0]
        current_polygon_length = current_segment["polygon_length"].values[0]
        print(f"Segment no: {str(i+1)}   {current_START_OP} - {current_END_OP} {str(current_polygon_length)}")

def parse_geo_shape(geo_shape_input):
    try:
        if isinstance(geo_shape_input, str):
            geo_shape_input = geo_shape_input.replace("'", '"')  # Normalize quotes
            geo_json = json.loads(geo_shape_input)
        elif isinstance(geo_shape_input, dict):
            geo_json = geo_shape_input
        else:
            logging.warning("Invalid geo shape input type")
            return []

        coords = geo_json.get("coordinates", [])
        if isinstance(coords, list) and all(isinstance(c, list) for c in coords):
            return coords

        logging.warning("Invalid geo shape structure")
        return []

    except Exception as e:
        logging.warning(f"Geo shape parse error: {e}")
        return []

def calculate_linestring_length(coords):
    try:
        if len(coords) < 2:
            return 0.0
        line = LineString(coords)
        return round(line.length, 2)
    except Exception as e:
        logger.warning(f"LineString calculation error: {e}")
        return 0.0

# ------------------------
# Main Stage 01 Function
# ------------------------
def choose_action(i, segment_df, CLOSENESS_THRESHOLD, NEVER_SKIP_LIST)->  tuple[pd.DataFrame, int]:
    print(f"i = {str(i)}")
    current_segment = segment_df.iloc[[i]]
    current_START_OP = current_segment["START_OP"].values[0]
    current_END_OP = current_segment["END_OP"].values[0]
    first_segment_check = is_first_segment(i)
    last_segment_check = is_last_segment(i, segment_df)
    current_polygon_length = current_segment["polygon_length"].values[0]
    print(f"Proccessing segment {current_START_OP} - {current_END_OP}")
    print(f"first_segment_check {first_segment_check} - last_segment_check {last_segment_check}")
    # ------------------------
    # POLYGON LENGTH IS ENOUGH
    # ------------------------
    if current_polygon_length > CLOSENESS_THRESHOLD:
        print(f"{current_START_OP} - {current_END_OP} is long enough")
        i+=1
        return segment_df, i
    
    #-----------------------------------------------------------------------------------------------------------------------
    # ------------------------
    # POLYGON LENGTH IS NOT ENOUGH
    # ------------------------
    # ------------------------
    # FIRST SEGMENT ACTIONS
    # ------------------------
    if last_segment_check == False and first_segment_check == True: # This is the first segment, and this is NOT the last segment
        # 2 Possibilities, remove it or combine it with next segment
        # First try to combine it with the next
        
        print(f"{current_START_OP} - {current_END_OP} is FIRST SEGMENT")
        if current_END_OP not in NEVER_SKIP_LIST:
            
            segment_df = combine_next_segment(segment_df, i) 
            return segment_df, i
        # If combination with next segment is not possible we try to remove the first segment
        if current_END_OP in NEVER_SKIP_LIST and current_START_OP not in NEVER_SKIP_LIST:
            
            segment_df = remove_first_segment(segment_df)
            return segment_df, i
    # ------------------------
    # MID SEGMENT ACTIONS
    # ------------------------
    #There are 2 possibilities for mid segments: Combine with next segment or combine with previous one
    if last_segment_check == False and first_segment_check == False: # This is NOT the first segment, and this is NOT the last segment
        print(f"{current_START_OP} - {current_END_OP} is MID SEGMENT")
        next_segment = segment_df.iloc[[i+1]]
        next_START_OP = next_segment["START_OP"].values[0]
        next_END_OP = next_segment["END_OP"].values[0]
        previous_segment = segment_df.iloc[[i-1]]
        previous_START_OP = previous_segment["START_OP"].values[0]
        previous_END_OP = previous_segment["END_OP"].values[0]
        if current_START_OP not in NEVER_SKIP_LIST and current_END_OP not in NEVER_SKIP_LIST and next_START_OP not in NEVER_SKIP_LIST and next_END_OP not in NEVER_SKIP_LIST:
            segment_df,i = combine_next_segment(segment_df, i)
            return segment_df, i
        if current_END_OP in NEVER_SKIP_LIST and previous_END_OP not in NEVER_SKIP_LIST:
            segment_df = combine_previous_segment(segment_df, i)
            return segment_df, i
    # ------------------------
    # LAST SEGMENT ACTIONS
    # ------------------------
    #There are 2 possibilities for last segments: Combine with previous segment or remove it
    # First we try to combine with previous one
    if last_segment_check == True and first_segment_check == False: # This is NOT the first segment, and this is the last segment
        print(f"{current_START_OP} - {current_END_OP} is LAST SEGMENT")
        previous_segment = segment_df.iloc[[i-1]]
        previous_START_OP = previous_segment["START_OP"].values[0]
        previous_END_OP = previous_segment["END_OP"].values[0]
        if current_START_OP not in NEVER_SKIP_LIST:
            segment_df, i = combine_previous_segment(segment_df, i)
            
            return segment_df, i
        if current_START_OP in NEVER_SKIP_LIST and current_END_OP not in NEVER_SKIP_LIST:
            segment_df = remove_last_segment(segment_df)
            return segment_df, i
def is_first_segment(i: int)->bool:
    segment = False
    if i == 0:
        segment = True
    return segment
def is_last_segment(i: int, segment_df: pd.DataFrame)->bool:
    
    segment = False
    last_row_index = len(segment_df)-1
    
    if i == last_row_index:
        segment = True
    return segment
def is_endOP_removable(current_END_OP: str, NEVER_SKIP_LIST: list)->bool:
    removable = True
    if current_END_OP in NEVER_SKIP_LIST:
        removable = False
    return removable
def is_startOP_removable(current_START_OP: str, NEVER_SKIP_LIST: list)->bool:
    removable = True
    if current_START_OP in NEVER_SKIP_LIST:
        removable = False
    return removable





def remove_first_segment(segment_df: pd.DataFrame) -> pd.DataFrame:
    if segment_df.empty:
        logger.warning("remove_first_segment: DataFrame is already empty.")
        return segment_df

    try:
        current_segment = segment_df.iloc[0]
        current_START_OP = current_segment["START_OP"]
        current_END_OP = current_segment["END_OP"]

        print(f"🗑️ REMOVE FIRST SEGMENT IS TRIGGERED for segment {current_START_OP} - {current_END_OP}")

        segment_df = segment_df.iloc[1:].reset_index(drop=True)

        if not segment_df.empty:
            next_segment = segment_df.iloc[0]
            new_START_OP = next_segment["START_OP"]
            new_END_OP = next_segment["END_OP"]
            print(f"➡️ New first segment is {new_START_OP} - {new_END_OP}")
        else:
            print("✅ DataFrame is now empty after removal.")

        return segment_df

    except Exception as e:
        logger.error(f"❌ remove_first_segment failed: {e}")
        return segment_df
def remove_last_segment(segment_df: pd.DataFrame) -> pd.DataFrame:
    if segment_df.empty:
        logger.warning("remove_last_segment: DataFrame is already empty.")
        return segment_df

    try:
        last_segment = segment_df.iloc[-1]
        last_START_OP = last_segment["START_OP"]
        last_END_OP = last_segment["END_OP"]

        print(f"🗑️ REMOVE LAST SEGMENT IS TRIGGERED for segment {last_START_OP} - {last_END_OP}")

        # Son satırı sil
        segment_df = segment_df.iloc[:-1].reset_index(drop=True)

        if not segment_df.empty:
            new_last = segment_df.iloc[-1]
            new_START_OP = new_last["START_OP"]
            new_END_OP = new_last["END_OP"]
            print(f"⬅️ New last segment is {new_START_OP} - {new_END_OP}")
        else:
            print("✅ DataFrame is now empty after removal.")

        return segment_df

    except Exception as e:
        logger.error(f"❌ remove_last_segment failed: {e}")
        return segment_df 
def combine_next_segment(segment_df: pd.DataFrame, i: int) -> tuple[pd.DataFrame, int]:
    try:
        # Get Rows
        current_segment = segment_df.iloc[i]
        next_segment = segment_df.iloc[i + 1]

        current_START_OP = current_segment["START_OP"]
        current_END_OP = current_segment["END_OP"]
        next_START_OP = next_segment["START_OP"]
        next_END_OP = next_segment["END_OP"]

        print(f"✅ combine_next_segment IS TRIGGERED for: {current_START_OP} - {current_END_OP} + {next_START_OP} - {next_END_OP}")

        # Merge geo shapes
        merged_geo_shape = merge_geo_shapes(current_segment["Geo shape"], next_segment["Geo shape"])
        merged_coordinates = parse_geo_shape(merged_geo_shape)
        combined_length = current_segment["polygon_length"] + next_segment["polygon_length"]

        # Build new combined row
        new_row = {
            "START_OP": current_segment["START_OP"],
            "END_OP": next_segment["END_OP"],
            "polygon_length": combined_length,
            "Geo shape": merged_geo_shape,
            "Linie": current_segment["Linie"],
            "KM START": current_segment["KM START"],
            "KM END": next_segment["KM END"],
            "number_of_polygon_points": len(merged_coordinates),
            "_coordinates": merged_coordinates
        }

        # Delete old rows
        segment_df = segment_df.drop(segment_df.index[[i, i + 1]]).reset_index(drop=True)

        # Add new combined row to df
        upper = segment_df.iloc[:i]
        lower = segment_df.iloc[i:]
        new_df = pd.concat([upper, pd.DataFrame([new_row]), lower], ignore_index=True)

        # don't change the i index
        return new_df, i

    except Exception as e:
        logger.error(f"❌ combine_next_segment failed at index {i}: {e}")
        return segment_df, i + 1  # hatalıysa bir sonraki segmenti dene
def combine_previous_segment(segment_df: pd.DataFrame, i: int) -> tuple[pd.DataFrame, int]:
    try:
        
        # Get rowss
        current_segment = segment_df.iloc[i]
        previous_segment = segment_df.iloc[i - 1]

        current_START_OP = current_segment["START_OP"]
        current_END_OP = current_segment["END_OP"]
        previous_START_OP = previous_segment["START_OP"]
        previous_END_OP = previous_segment["END_OP"]

        print(f"✅ combine_previous_segment IS TRIGGERED for: {previous_START_OP} - {previous_END_OP} + {current_START_OP} - {current_END_OP}")

        # Merge geo shapes
        merged_geo_shape = merge_geo_shapes(previous_segment["Geo shape"], current_segment["Geo shape"])
        merged_coordinates = parse_geo_shape(merged_geo_shape)
        combined_length = previous_segment["polygon_length"] + current_segment["polygon_length"]

        # Build new row
        new_row = {
            "START_OP": previous_segment["START_OP"],
            "END_OP": current_segment["END_OP"],
            "polygon_length": combined_length,
            "Geo shape": merged_geo_shape,
            "Linie": previous_segment["Linie"],  # ya da current_segment, fark yoksa
            "KM START": previous_segment["KM START"],
            "KM END": current_segment["KM END"],
            "number_of_polygon_points": len(merged_coordinates),
            "_coordinates": merged_coordinates
        }

        # Delete two old rows
        segment_df = segment_df.drop(segment_df.index[[i - 1, i]]).reset_index(drop=True)

        # Add new combined row
        upper = segment_df.iloc[:i - 1]
        lower = segment_df.iloc[i - 1:]
        new_df = pd.concat([upper, pd.DataFrame([new_row]), lower], ignore_index=True)

        # i-1 konumundaki yeni birleşmiş satırı tekrar incelemek isteyebiliriz
        return new_df, i - 1

    except Exception as e:
        logger.error(f"❌ combine_previous_segment failed at index {i}: {e}")
        return segment_df, i + 1  # hata varsa ilerlemeye devam et

def run():
    logger.info("Stage 01 started: Clean and analyze line segment geometries")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        df = pd.read_csv(POLYGON_FILE, delimiter=";")
        logger.info(f"Loaded input file: {POLYGON_FILE} ({len(df)} rows)")
    except Exception as e:
        logger.error(f"CSV loading failed: {e}")
        return
    df = df[df['Linie'].isin(LINE_ID_LIST)].copy()
    logger.info(f"Filtered by LINE_ID_LIST. Remaining rows: {len(df)}")

    df["_coordinates"] = df["Geo shape"].apply(parse_geo_shape)
    df["polygon_length"] = df["_coordinates"].apply(calculate_linestring_length)
    df["number_of_polygon_points"] = df["_coordinates"].apply(lambda x: len(x))

    keep_cols = [
        "Linie", "START_OP", "END_OP", "KM START", "KM END",
        "polygon_length", "number_of_polygon_points", "Geo shape", "_coordinates"
    ]
    df = df[keep_cols].reset_index(drop=True)
    total_lines = len(LINE_ID_LIST)
    for idx, line_id in enumerate(LINE_ID_LIST, start=1):

        print(f"\nProgress: Currently processing Line no {idx} of total {total_lines} Lines")
        current_line_id = line_id
        segment_df = df[df["Linie"] == line_id].sort_values("KM START").reset_index(drop=True)
        print_all_segments(segment_df)
        i = 0
        while i in range(0,len(segment_df)):
           segment_df, i = choose_action(i, segment_df,  CLOSENESS_THRESHOLD, NEVER_SKIP_LIST)
    df.to_csv(OUTPUT_POLYGON_FILE, index=False, encoding='utf-8-sig')
    print(f"✍️ File saved at: {OUTPUT_POLYGON_FILE.resolve()}")
    print(f"Final Version of segments")
    print_all_segments(segment_df)
