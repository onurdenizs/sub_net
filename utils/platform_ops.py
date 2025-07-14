import pandas as pd
from typing import Dict, Any
import statistics
import logging
import json
from utils.constants import (
    MAX_PLATFORM_COUNT, MIN_PLATFORM_COUNT, DEFAULT_PLATFORM_COUNT,
    MIN_PLATFORM_LENGTH, MAX_PLATFORM_LENGTH, DEFAULT_PLATFORM_LENGTH,
    PLATFORM_LENGTH_DECISION_METHOD, FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH, FILL_EMPTY_PLATFORM_NO_DATA_WITH,FILTERED_SUB_NETWORK_POLYGON_FILE, ENTRY_OFFSET_BUFFER
)

from utils.segment_ops import (
    parse_geo_shape,
    calculate_linestring_length,
    merge_geo_shapes,
    is_first_segment,
    is_last_segment,
    combine_next_segment,
    combine_previous_segment,
    remove_first_segment,
    remove_last_segment
)


def filter_perron_data(perron_df, unique_ops):
    """
    Filter perronkante data to only include stations in unique_ops.

    Args:
        perron_df (pd.DataFrame): Original perronkante DataFrame.
        unique_ops (set): Set of station abbreviations to keep.

    Returns:
        pd.DataFrame: Filtered DataFrame.
    """
    return perron_df[perron_df['Station abbreviation'].isin(unique_ops)].copy()


def get_station_tracks(current_station_perron_df):
    """
    Get unique platform numbers for a station.

    Args:
        current_station_perron_df (pd.DataFrame): Subset DataFrame for one station.

    Returns:
        set: Unique platform numbers.
    """
    return set(current_station_perron_df['Platform number'].dropna().unique())


def calculate_platform_lengths(current_station_perron_df, op, logger):
    """
    Calculate min, max, avg platform lengths for a station.

    Args:
        current_station_perron_df (pd.DataFrame): Subset DataFrame for one station.
        op (str): Station abbreviation.
        logger (logging.Logger): Logger instance.

    Returns:
        tuple: (min_length, max_length, avg_length, platform_count)
    """
    unique_tracks = get_station_tracks(current_station_perron_df)
    track_lengths = []

    for track in unique_tracks:
        length = current_station_perron_df[current_station_perron_df['Platform number'] == track]["Length of platform edge"].sum()
        track_lengths.append(length)

    if track_lengths:
        min_len = min(track_lengths)
        max_len = max(track_lengths)
        avg_len = statistics.mean(track_lengths)
        logger.debug(f"{op} min: {min_len}, max: {max_len}, avg: {avg_len}")
        return min_len, max_len, avg_len, len(unique_tracks)
    else:
        logger.warning(f"⚠️ Station {op} has no valid platform length info in customer tracks.")
        return None, None, None, 0


def decide_platform_length(min_len, max_len, avg_len):
    """
    Decide final platform length using decision method.

    Args:
        min_len (float): Minimum length.
        max_len (float): Maximum length.
        avg_len (float): Average length.

    Returns:
        float: Final decided platform length.
    """
    if PLATFORM_LENGTH_DECISION_METHOD == "X":
        return min(MAX_PLATFORM_LENGTH, max_len)
    elif PLATFORM_LENGTH_DECISION_METHOD == "N":
        return max(MIN_PLATFORM_LENGTH, min_len)
    elif PLATFORM_LENGTH_DECISION_METHOD == "A":
        return max(MIN_PLATFORM_LENGTH, min(MAX_PLATFORM_LENGTH, avg_len))
    else:
        return DEFAULT_PLATFORM_LENGTH


def get_fallback_values():
    """
    Get fallback values when station has no data.

    Returns:
        tuple: (platform_length, platform_count)
    """
    if FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH == "X":
        platform_length = MAX_PLATFORM_LENGTH
    elif FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH == "N":
        platform_length = MIN_PLATFORM_LENGTH
    else:
        platform_length = DEFAULT_PLATFORM_LENGTH

    if FILL_EMPTY_PLATFORM_NO_DATA_WITH == "X":
        platform_count = MAX_PLATFORM_COUNT
    elif FILL_EMPTY_PLATFORM_NO_DATA_WITH == "N":
        platform_count = MIN_PLATFORM_COUNT
    else:
        platform_count = DEFAULT_PLATFORM_COUNT

    return platform_length, platform_count

def find_direction_between_coordinates(coord1, coord2):
    """
    Determine if coord2 is East or West relative to coord1.

    Args:
        coord1 (list or tuple): [X1, Y1] coordinate.
        coord2 (list or tuple): [X2, Y2] coordinate.

    Returns:
        str: "East" if coord2 is east of coord1,
             "West" if coord2 is west of coord1,
             "Same" if X coordinates are equal.
    """
    x1 = coord1[0]
    x2 = coord2[0]

    if x2 > x1:
        return "East"
    elif x2 < x1:
        return "West"
    else:
        return "Same"

def process_station_platform_info(perron_df, unique_ops, logger) -> pd.DataFrame:
    """
    Main processing function to generate platform info DataFrame.

    Args:
        perron_df (pd.DataFrame): Filtered perronkante DataFrame.
        unique_ops (set): Set of station abbreviations.
        logger (logging.Logger): Logger instance.

    Returns:
        pd.DataFrame: Final DataFrame with platform info.
    """
    processed_rows = []

    for idx, op in enumerate(unique_ops, 1):
        logger.info(f"📊 Station {idx}/{len(unique_ops)}: {op}")
        current_station_perron_df = perron_df[perron_df['Station abbreviation'] == op].copy()
        logger.debug("\n" + current_station_perron_df.to_string())

        if current_station_perron_df.empty:
            logger.debug(f"Station {op} has no platform data, using fallback values.")
            platform_length, platform_count = get_fallback_values()
            min_len = max_len = avg_len = platform_length
        else:
            min_len, max_len, avg_len, platform_count = calculate_platform_lengths(current_station_perron_df, op, logger)
            if min_len is None:
                platform_length, platform_count = get_fallback_values()
                min_len = max_len = avg_len = platform_length
            else:
                platform_length = decide_platform_length(min_len, max_len, avg_len)
                if platform_count > MAX_PLATFORM_COUNT:
                    platform_count = MAX_PLATFORM_COUNT
                elif platform_count < MIN_PLATFORM_COUNT:
                    platform_count = MIN_PLATFORM_COUNT

        result = {
            "station": op,
            "minimum_platform_length": min_len,
            "maximum_platform_length": max_len,
            "average_platform_length": avg_len,
            "platform_length": platform_length,
            "platform_count": platform_count
        }
        processed_rows.append(result)

    platform_df = pd.DataFrame(processed_rows)
    return platform_df
def find_station_connections(platform_df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    """
    Determine connected stations and their directions (West or East) 
    based on filtered polygon segments.

    Args:
        platform_df (pd.DataFrame): Platform DataFrame with station list.

    Returns:
        pd.DataFrame: Updated DataFrame with 'connected_stations' column.
    """


    polygon_df = pd.read_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, delimiter=';')
    platform_df['connected_stations'] = platform_df.apply(
        lambda row: {'West': set(), 'East': set()}, axis=1
    )

    for idx, row in polygon_df.iterrows():
        start_op = row['START_OP']
        end_op = row['END_OP']
        coords = parse_geo_shape(row['Geo shape'])

        if not coords or len(coords) < 2:
            logging.warning(f"⚠️ Segment {start_op}-{end_op} has insufficient coordinates.")
            continue

        # First direction: start -> end
        dir_start_to_end = find_direction_between_coordinates(coords[0], coords[1])

        # Reverse direction: end -> start
        dir_end_to_start = find_direction_between_coordinates(coords[-1], coords[-2])

        # Update start_op's connected_stations
        start_idx = platform_df[platform_df['station'] == start_op].index
        if not start_idx.empty and dir_start_to_end in ['West', 'East']:
            platform_df.at[start_idx[0], 'connected_stations'][dir_start_to_end].add(end_op)

        # Update end_op's connected_stations
        end_idx = platform_df[platform_df['station'] == end_op].index
        if not end_idx.empty and dir_end_to_start in ['West', 'East']:
            platform_df.at[end_idx[0], 'connected_stations'][dir_end_to_start].add(start_op)

    return platform_df


def define_station_types(platform_df: pd.DataFrame) -> pd.DataFrame:
    """
    Processing function for station types.
    Decides station type based on connections.
    """
    platform_df['type'] = "isolated"
    for idx, row in platform_df.iterrows():
        connected_stations = row['connected_stations']
        if connected_stations is not None:
            west_connections = connected_stations.get('West', [])
            east_connections = connected_stations.get('East', [])
            

            if len(west_connections) > 0 and len(east_connections) > 0:
                platform_df.at[idx, 'type'] = "two-way"
            elif len(west_connections) > 0 or len(east_connections) > 0:
                platform_df.at[idx, 'type'] = "single-direction"
            else:
                platform_df.at[idx, 'type'] = "isolated"
    return platform_df

def assign_center_coordinates(platform_df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    """
    Finds the center coordinate of each station with the following logic:
    For each segment A->B, the first coordinate is A's center, the last coordinate is B's center.

    Args:
        platform_df (pd.DataFrame): Platform DataFrame.

    Returns:
        pd.DataFrame: Updated DataFrame with 'center_coordinates' column.
    """


    polygon_df = pd.read_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, delimiter=';')
    platform_df['center_coordinates'] = None  # Start with None

    for idx, row in polygon_df.iterrows():
        start_op = row["START_OP"]
        end_op = row["END_OP"]
        coords = parse_geo_shape(row['Geo shape'])

        if coords:
            start_coord = coords[0]
            end_coord = coords[-1]

            # Assign start_op
            try:
                start_idx = platform_df.loc[platform_df["station"] == start_op].index[0]
                start_value = platform_df.at[start_idx, "center_coordinates"]

                if start_value is None or (isinstance(start_value, float) and pd.isna(start_value)):
                    platform_df.at[start_idx, "center_coordinates"] = [start_coord[0], start_coord[1]]

            except IndexError:
                logger.warning(f"⚠️ start_op '{start_op}' not found in platform_df")

            # Assign end_op
            try:
                end_idx = platform_df.loc[platform_df["station"] == end_op].index[0]
                end_value = platform_df.at[end_idx, "center_coordinates"]

                if end_value is None or (isinstance(end_value, float) and pd.isna(end_value)):
                    platform_df.at[end_idx, "center_coordinates"] = [end_coord[0], end_coord[1]]

            except IndexError:
                logger.warning(f"⚠️ end_op '{end_op}' not found in platform_df")

        else:
            logger.warning(f"⚠️ No coordinates found for segment {row.get('LINE_ID', 'UNKNOWN')}")

    return platform_df

def compute_entry_nodes_json(platform_df: pd.DataFrame, logger: logging.Logger) -> Dict[str, Dict[str, Any]]:
    """
    Compute entry node coordinates for each station based on connected segments,
    returning a JSON-serializable dictionary without modifying the input DataFrame.

    Args:
        platform_df (pd.DataFrame): DataFrame with station info, must include:
            'station', 'center_coordinates', 'platform_length', 'connected_stations'.
        logger (logging.Logger): Logger instance.

    Returns:
        Dict[str, Dict[str, Any]]: Dictionary with station codes as keys and their
        entry node coordinates as nested dicts, e.g.,
        {'TUE': {'West': [x, y], 'East': [x, y]}, ...}.
    """
    try:
        polygon_df = pd.read_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, delimiter=';')
        entry_nodes_result: Dict[str, Dict[str, Any]] = {}

        for idx, row in platform_df.iterrows():
            op = row['station']
            platform_length = row['platform_length']
            connected = row['connected_stations']
            center_coord = row['center_coordinates']

            # Deserialize JSON string if necessary
            if isinstance(center_coord, str):
                center_coord = json.loads(center_coord)
            if isinstance(connected, str):
                connected = json.loads(connected.replace("'", '"'))

            entry_coords: Dict[str, Any] = {}
            offset_meters = platform_length / 2 + ENTRY_OFFSET_BUFFER

            for direction in ['West', 'East']:
                neighbors = connected.get(direction, [])
                if not neighbors:
                    continue

                found = False
                for neighbor in neighbors:
                    segment = polygon_df[
                        ((polygon_df['START_OP'] == op) & (polygon_df['END_OP'] == neighbor)) |
                        ((polygon_df['START_OP'] == neighbor) & (polygon_df['END_OP'] == op))
                    ]

                    if segment.empty:
                        continue

                    seg_coords = parse_geo_shape(segment.iloc[0]['Geo shape'])
                    seg_length = segment.iloc[0]['polygon_length']
                    num_points = int(segment.iloc[0]['number_of_polygon_points'])

                    if seg_length == 0 or num_points < 2:
                        logger.warning(f"⚠️ Invalid segment between {op} and {neighbor}")
                        continue

                    avg_step = seg_length / (num_points - 1)
                    num_steps = int(offset_meters / avg_step)

                    if segment.iloc[0]['START_OP'] == op:
                        selected_coord = seg_coords[min(num_steps, len(seg_coords) - 1)]
                    else:
                        selected_coord = seg_coords[max(len(seg_coords) - num_steps - 1, 0)]

                    entry_coords[direction] = [selected_coord[0], selected_coord[1]]
                    found = True
                    break  # only take first valid neighbor

                if not found:
                    logger.warning(f"⚠️ Could not compute {direction} entry for station {op}")

            entry_nodes_result[op] = entry_coords

        logger.info(f"✅ Computed entry node coordinates for {len(entry_nodes_result)} stations")
        return entry_nodes_result

    except Exception as e:
        logger.error(f"❌ Failed to compute entry nodes: {e}")
        raise    

