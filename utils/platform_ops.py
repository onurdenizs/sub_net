import pandas as pd
import statistics
import logging
import json
from typing import Dict, Any
import ast
from utils.constants import (
    MAX_PLATFORM_COUNT, MIN_PLATFORM_COUNT, DEFAULT_PLATFORM_COUNT,
    MIN_PLATFORM_LENGTH, MAX_PLATFORM_LENGTH, DEFAULT_PLATFORM_LENGTH,
    PLATFORM_LENGTH_DECISION_METHOD, FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH,
    FILL_EMPTY_PLATFORM_NO_DATA_WITH, FILTERED_SUB_NETWORK_POLYGON_FILE, ENTRY_OFFSET_BUFFER
)
from utils.segment_ops import parse_geo_shape

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

def filter_perron_data(perron_df, unique_ops):
    return perron_df[perron_df['Station abbreviation'].isin(unique_ops)].copy()


def get_station_tracks(current_station_perron_df):
    return set(current_station_perron_df['Platform number'].dropna().unique())


def calculate_platform_lengths(current_station_perron_df, op, logger):
    unique_tracks = get_station_tracks(current_station_perron_df)
    track_lengths = [
        current_station_perron_df[current_station_perron_df['Platform number'] == track]["Length of platform edge"].sum()
        for track in unique_tracks
    ]

    if track_lengths:
        min_len = min(track_lengths)
        max_len = max(track_lengths)
        avg_len = statistics.mean(track_lengths)
        logger.debug(f"{op} min: {min_len}, max: {max_len}, avg: {avg_len}")
        return min_len, max_len, avg_len, len(unique_tracks)
    else:
        logger.warning(f"⚠️ Station {op} has no valid platform length info.")
        return None, None, None, 0


def decide_platform_length(min_len, max_len, avg_len):
    if PLATFORM_LENGTH_DECISION_METHOD == "X":
        return min(MAX_PLATFORM_LENGTH, max_len)
    elif PLATFORM_LENGTH_DECISION_METHOD == "N":
        return max(MIN_PLATFORM_LENGTH, min_len)
    elif PLATFORM_LENGTH_DECISION_METHOD == "A":
        return max(MIN_PLATFORM_LENGTH, min(MAX_PLATFORM_LENGTH, avg_len))
    else:
        return DEFAULT_PLATFORM_LENGTH


def get_fallback_values():
    length = {
        "X": MAX_PLATFORM_LENGTH,
        "N": MIN_PLATFORM_LENGTH
    }.get(FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH, DEFAULT_PLATFORM_LENGTH)

    count = {
        "X": MAX_PLATFORM_COUNT,
        "N": MIN_PLATFORM_COUNT
    }.get(FILL_EMPTY_PLATFORM_NO_DATA_WITH, DEFAULT_PLATFORM_COUNT)

    return length, count


def build_station_info(polygon_df, perron_df, logger) -> pd.DataFrame:
    unique_ops = set(polygon_df['START_OP']).union(polygon_df['END_OP'])
    
    # Melt START_OP and END_OP, keep Linie as id
    station_line_map = (
        polygon_df[['START_OP', 'END_OP', 'Linie']]
        .melt(id_vars=['Linie'], value_name='station')[['station', 'Linie']]
        .drop_duplicates()
        .groupby('station')['Linie'].apply(list)
        .to_dict()
    )

    processed_rows = []
    
    for idx, op in enumerate(unique_ops, 1):
        logger.info(f"📊 Station {idx}/{len(unique_ops)}: {op}")
        current_station_perron_df = perron_df[perron_df['Station abbreviation'] == op]

        if current_station_perron_df.empty:
            platform_length, platform_count = get_fallback_values()
            min_len = max_len = avg_len = platform_length
        else:
            min_len, max_len, avg_len, platform_count = calculate_platform_lengths(current_station_perron_df, op, logger)
            if min_len is None:
                platform_length, platform_count = get_fallback_values()
                min_len = max_len = avg_len = platform_length
            else:
                platform_length = decide_platform_length(min_len, max_len, avg_len)
                platform_count = max(MIN_PLATFORM_COUNT, min(MAX_PLATFORM_COUNT, platform_count))

        result = {
            "station": op,
            "minimum_platform_length": min_len,
            "maximum_platform_length": max_len,
            "average_platform_length": avg_len,
            "decided_platform_length": platform_length,
            "platform_count": platform_count,
            "line_ids": station_line_map.get(op, [])
        }
        processed_rows.append(result)
    platform_df = pd.DataFrame(processed_rows)
    platform_df.sort_values(by='station', inplace=True)
    platform_df.reset_index(drop=True, inplace=True)
    return platform_df


def find_station_connections(platform_df: pd.DataFrame,polygon_df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    """
    Determine connected stations and their directions (West or East) 
    based on filtered polygon segments.

    Args:
        platform_df (pd.DataFrame): Platform DataFrame with station list.

    Returns:
        pd.DataFrame: Updated DataFrame with 'connected_stations' column.
    """


    
    platform_df['connected_stations'] = platform_df.apply(
        lambda row: {'West': set(), 'East': set()}, axis=1
    )

    for idx, row in polygon_df.iterrows():
        start_op = row['START_OP']
        end_op = row['END_OP']
        coords = parse_geo_shape(row['Geo shape'])

        if not coords or len(coords) < 2:
            logger.warning(f"⚠️ Segment {start_op}-{end_op} has insufficient coordinates.")
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
    
    platform_df.sort_values(by='station', inplace=True)
    platform_df.reset_index(drop=True, inplace=True)
    return platform_df



def define_station_types(platform_df: pd.DataFrame) -> pd.DataFrame:
    platform_df['type'] = platform_df['connected_stations'].apply(
        lambda conn: 'two-way' if conn['West'] and conn['East'] else ('single-direction' if conn['West'] or conn['East'] else 'isolated')
    )
    platform_df.sort_values(by='station', inplace=True)
    platform_df.reset_index(drop=True, inplace=True)
    return platform_df

def find_entry_nodes(platform_df: pd.DataFrame,polygon_df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    platform_df['entry_nodes'] = platform_df.apply(lambda row: [], axis=1)

    for idx, row in platform_df.iterrows():
        logger.info(f"📊 Finding Station {idx+1}/{len(platform_df)} entry nodes")
        connections_dict = row['connected_stations']
        
        directions = connections_dict.keys()
        for direction in directions:
            if list(connections_dict[direction]):
                
                for con_sta in list(connections_dict[direction]):
                    start=polygon_df[polygon_df['START_OP']==row['station']]
                    
                    start_segment=start[start['END_OP']==con_sta]
                    
                    end=polygon_df[polygon_df['END_OP']==row['station']]
                    
                    end_segment=end[end['START_OP']==con_sta]
                    
                    if not start_segment.empty:
                        if len(start_segment) == 1:
                            
                            polygon_length = start_segment['polygon_length'].round(2).iloc[0]
                            num_of_coords = start_segment['number_of_polygon_points'].iloc[0]
                            line_id = int(start_segment['Linie'].iloc[0])
                            average_polygon_coord_dist = round(polygon_length/num_of_coords)
                            platform_length = int(row['decided_platform_length'])
                            print(platform_length)
                            total_entry_offset = int(ENTRY_OFFSET_BUFFER + platform_length/2)
                            number_of_entr_coord_points = int(total_entry_offset/average_polygon_coord_dist)
                            logger.info(f"FOUND SEGMENT for station {row['station']}: Direction: {direction} - Line ID: {line_id} - {start_segment['START_OP'].to_string(index=False)} - {start_segment['END_OP'].to_string(index=False)} length: {str(polygon_length)}")
                            if number_of_entr_coord_points >= num_of_coords:
                                logger.warning(f" Segment  {start_segment['START_OP'].to_string(index=False)} - {start_segment['END_OP'].to_string(index=False)} of Line ID: {line_id} has {str(num_of_coords)} but entry node needs {str(number_of_entr_coord_points)}")
                            else:
                                
                                coords = start_segment['_coordinates'].iloc[0]
                                coords_list = ast.literal_eval(coords)
                                entr_coords = coords_list[number_of_entr_coord_points]
                                entry_node_dict = {"Direction": direction, "Connected Station": con_sta, "Line": line_id, "Coordinates": entr_coords}
                                row['entry_nodes'].append(entry_node_dict)
                        elif len(start_segment) > 1:
                            print("Çok segment buldum")
                            print(f"FOUND SEGMENT for station {row['station']}: Direction: {direction} -Line ID: {line_id} -  {start_segment['START_OP'].to_string(index=False)} - {start_segment['END_OP'].to_string(index=False)} length: {str(polygon_length)}")
                        
                    
                    elif not end_segment.empty:
                        
                        if len(end_segment) == 1:
                            
                            polygon_length = end_segment['polygon_length'].round(2).iloc[0]
                            num_of_coords = end_segment['number_of_polygon_points'].iloc[0]
                            line_id = int(end_segment['Linie'].iloc[0])
                            average_polygon_coord_dist = round(polygon_length/num_of_coords)
                            platform_length = int(row['decided_platform_length'])
                            print(platform_length)
                            total_entry_offset = int(ENTRY_OFFSET_BUFFER + platform_length/2)
                            number_of_entr_coord_points = int(total_entry_offset/average_polygon_coord_dist)
                            entry_node_coord_index = number_of_entr_coord_points * -1
                            logger.info(f"FOUND SEGMENT for station {row['station']}: Direction: {direction} - Line ID: {line_id} - {end_segment['START_OP'].to_string(index=False)} - {end_segment['END_OP'].to_string(index=False)} length: {str(polygon_length)}")
                            if number_of_entr_coord_points >= num_of_coords:
                                logger.warning(f" Segment  {start_segment['START_OP'].to_string(index=False)} - {start_segment['END_OP'].to_string(index=False)} of Line ID: {line_id} has {str(num_of_coords)} but entry node needs {str(number_of_entr_coord_points)}")
                            else:
                                
                                coords = end_segment['_coordinates'].iloc[0]
                                coords_list = ast.literal_eval(coords)
                                entr_coords = coords_list[entry_node_coord_index]
                                entry_node_dict = {"Direction": direction, "Connected Station": con_sta, "Line": line_id, "Coordinates": entr_coords}
                                row['entry_nodes'].append(entry_node_dict)
                        elif len(end_segment) > 1:
                            print("Çok segment buldum")
                            print(f"FOUND SEGMENT for station {row['station']}: Direction: {direction} - Line ID: {line_id} - {end_segment['START_OP'].to_string(index=False)} - {end_segment['END_OP'].to_string(index=False)} length: {str(polygon_length)}")
                    #if len(start_segment) > 0:
                        #print(f"found start segment with: {row['station']}: {len(start_segment)}")
                        #print(f"Segment: {start_segment['START_OP']} - {start_segment['END_OP']} - {start_segment['polygon_length']} meters")
                    #elif len(end_segment) > 0:
                        #print(f"found end segment with: {row['station']}: {len(end_segment)}")
                        #print(f"Segment: {end_segment['START_OP']} - {end_segment['END_OP']} - {end_segment['polygon_length']} meters")
                                   
                                   
                
    platform_df.sort_values(by='station', inplace=True)
    platform_df.reset_index(drop=True, inplace=True)
    return platform_df