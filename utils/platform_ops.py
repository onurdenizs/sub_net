import pandas as pd
import statistics
import logging
from utils.constants import (
    MAX_PLATFORM_COUNT, MIN_PLATFORM_COUNT, DEFAULT_PLATFORM_COUNT,
    MIN_PLATFORM_LENGTH, MAX_PLATFORM_LENGTH, DEFAULT_PLATFORM_LENGTH,
    PLATFORM_LENGTH_DECISION_METHOD, FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH, FILL_EMPTY_PLATFORM_NO_DATA_WITH,FILTERED_SUB_NETWORK_POLYGON_FILE
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
def find_station_connections(platform_df: pd.DataFrame) -> pd.DataFrame:
    """
    processing function to read filtered polygon data by line ids (Linie column) and at each row decide connected stations and their directions (west or east).

    Args:
        platform_df (pd.DataFrame): Filtered polygon DataFrame.
        

    Returns:
        pd.DataFrame: Final DataFrame with platform info.
    """
    polygon_df = pd.read_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, delimiter=';')
    unique_linie_list = polygon_df["Linie"].unique().tolist()
    
    platform_df['connected_stations'] = platform_df.apply(
    lambda row: {'West': set(), 'East': set()}, axis=1
    )
    
    for idx, line_id in enumerate(unique_linie_list, 1):
        current_line_segments = polygon_df[polygon_df["Linie"] == line_id].copy()
        
        for idy, row in current_line_segments.iterrows():
            

            coords = parse_geo_shape(row['Geo shape'])
            second_station_relative_to_first = find_direction_between_coordinates(coords[0], coords[1])
            index_start_op = platform_df[platform_df['station'] == row['START_OP']].index
            index_end_op = platform_df[platform_df['station'] == row['END_OP']].index
            
            if not index_start_op.empty:
                ids = index_start_op[0]
                platform_df.at[ids, 'connected_stations'][second_station_relative_to_first].add(row['END_OP'])
                if second_station_relative_to_first == "West":
                    ide = index_end_op[0]
                    platform_df.at[ide, 'connected_stations']["East"].add(row['START_OP'])
                elif second_station_relative_to_first == "East":
                    ide = index_end_op[0]
                    platform_df.at[ide, 'connected_stations']["West"].add(row['START_OP'])

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
            print(f"west_connections: {west_connections} len: {len(west_connections)}")
            print(f"east_connections: {east_connections} len: {len(east_connections)}")

            if len(west_connections) > 0 and len(east_connections) > 0:
                platform_df.at[idx, 'type'] = "two-way"
            elif len(west_connections) > 0 or len(east_connections) > 0:
                platform_df.at[idx, 'type'] = "single-direction"
            else:
                platform_df.at[idx, 'type'] = "isolated"
    return platform_df



        

