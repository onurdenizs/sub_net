import pandas as pd
import logging
import json
from shapely.geometry import LineString
from typing import Tuple

def print_all_segments(segment_df: pd.DataFrame ):
    """
    Print all segments in the DataFrame with their index, start, end, and polygon length.

    Args:
        segment_df (pd.DataFrame): DataFrame containing segment data.
    """
    print(f"Number of Total segments found: {str(len(segment_df))}")
    print(print(segment_df.columns))
    for i in range(0,len(segment_df)):
        current_segment = segment_df.iloc[[i]]
        current_START_OP = current_segment["START_OP"].values[0]
        current_END_OP = current_segment["END_OP"].values[0]
        current_polygon_length = current_segment["polygon_length"].values[0]
        print(f"Segment no: {str(i+1)}   {current_START_OP} - {current_END_OP} {str(current_polygon_length)}")


def is_first_segment(i: int) -> bool:
    """
    Check if the current index is the last segment.

    Args:
        i (int): Index to check.
        df (pd.DataFrame): DataFrame containing segment data.

    Returns:
        bool: True if last segment, False otherwise.
    """
    return i == 0

def is_last_segment(i: int, df: pd.DataFrame) -> bool:
    """
    Check if the current index is the last segment.

    Args:
        i (int): Index to check.
        df (pd.DataFrame): DataFrame containing segment data.

    Returns:
        bool: True if last segment, False otherwise.
    """
    return i == len(df) - 1

def parse_geo_shape(geo_shape_str: str) -> list:
    """
    Parse a GeoJSON-style geometry string into a list of coordinates.

    Args:
        geo_shape_str (str): GeoJSON string.

    Returns:
        list: List of coordinate pairs, or empty list if parse fails.
    """
    try:
        if isinstance(geo_shape_str, str):
            geo_shape_str = geo_shape_str.replace("'", '"')  # Normalize quotes
            geo_json = json.loads(geo_shape_str)
            coords = geo_json.get("coordinates", [])
            if isinstance(coords, list) and all(isinstance(c, list) for c in coords):
                return coords
        logging.warning("Invalid geo shape structure")
        return []
    except Exception as e:
        logging.warning(f"Geo shape parse error: {e}")
        return []

def calculate_linestring_length(coords: list) -> float:
    """
    Calculate the length of a LineString defined by coordinates.

    Args:
        coords (list): List of coordinate pairs.

    Returns:
        float: LineString length (in same units as coordinates), or 0.0 if invalid.
    """
    try:
        if len(coords) < 2:
            return 0.0
        line = LineString(coords)
        return round(line.length, 2)
    except Exception as e:
        logging.warning(f"LineString calculation error: {e}")
        return 0.0

def merge_geo_shapes(geo1: str, geo2: str) -> str:
    """
    Merge two GeoJSON LineStrings into a single LineString.

    Args:
        geo1 (str): GeoJSON string of first segment.
        geo2 (str): GeoJSON string of second segment.

    Returns:
        str: Merged GeoJSON string.
    """
    coords1 = parse_geo_shape(geo1)
    coords2 = parse_geo_shape(geo2)
    if coords1 and coords2 and coords1[-1] == coords2[0]:
        merged_coords = coords1 + coords2[1:]  # Avoid duplicating the shared point
    else:
        merged_coords = coords1 + coords2

    merged_shape = {
        "type": "LineString",
        "coordinates": merged_coords
    }
    return json.dumps(merged_shape)

def combine_next_segment(df: pd.DataFrame, i: int) -> Tuple[pd.DataFrame, int]:
    """
    Combine the current segment with the next one.

    Args:
        df (pd.DataFrame): DataFrame containing segment data.
        i (int): Current index.

    Returns:
        Tuple[pd.DataFrame, int]: Updated DataFrame and current index (re-evaluate merged row).
    """
    try:
        current_segment = df.iloc[[i]]
        next_segment = df.iloc[[i + 1]]
        merged_geo_shape = merge_geo_shapes(current_segment["Geo shape"].values[0], next_segment["Geo shape"].values[0])
        merged_coords = parse_geo_shape(merged_geo_shape)

        new_row = {
            "START_OP": current_segment["START_OP"].values[0],
            "END_OP": next_segment["END_OP"].values[0],
            "polygon_length": calculate_linestring_length(merged_coords),
            "Geo shape": merged_geo_shape,
            "Linie": current_segment["Linie"].values[0],
            "KM START": current_segment["KM START"].values[0],
            "KM END": next_segment["KM END"].values[0],
            "number_of_polygon_points": len(merged_coords),
            "_coordinates": merged_coords
        }

        df = df.drop(df.index[[i, i + 1]]).reset_index(drop=True)
        upper = df.iloc[:i]
        lower = df.iloc[i:]
        df = pd.concat([upper, pd.DataFrame([new_row]), lower], ignore_index=True)
        return df, i
    except Exception as e:
        logging.error(f"combine_next_segment failed at index {i}: {e}")
        return df, i + 1

def combine_previous_segment(df: pd.DataFrame, i: int) -> Tuple[pd.DataFrame, int]:
    """
    Combine the current segment with the previous one.

    Args:
        df (pd.DataFrame): DataFrame containing segment data.
        i (int): Current index.

    Returns:
        Tuple[pd.DataFrame, int]: Updated DataFrame and new index (points to merged row).
    """
    try:
        prev_segment = df.iloc[[i - 1]]
        current_segment = df.iloc[[i]]
        merged_geo_shape = merge_geo_shapes(prev_segment["Geo shape"].values[0], current_segment["Geo shape"].values[0])
        merged_coords = parse_geo_shape(merged_geo_shape)

        new_row = {
            "START_OP": prev_segment["START_OP"].values[0],
            "END_OP": current_segment["END_OP"].values[0],
            "polygon_length": calculate_linestring_length(merged_coords),
            "Geo shape": merged_geo_shape,
            "Linie": current_segment["Linie"].values[0],
            "KM START": prev_segment["KM START"].values[0],
            "KM END": current_segment["KM END"].values[0],
            "number_of_polygon_points": len(merged_coords),
            "_coordinates": merged_coords
        }

        df = df.drop(df.index[[i - 1, i]]).reset_index(drop=True)
        upper = df.iloc[:i - 1]
        lower = df.iloc[i - 1:]
        df = pd.concat([upper, pd.DataFrame([new_row]), lower], ignore_index=True)
        return df, i - 1
    except Exception as e:
        logging.error(f"combine_previous_segment failed at index {i}: {e}")
        return df, i + 1

def remove_first_segment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove the first segment from the DataFrame.

    Args:
        df (pd.DataFrame): DataFrame containing segment data.

    Returns:
        pd.DataFrame: Updated DataFrame with first row removed.
    """
    try:
        return df.iloc[1:].reset_index(drop=True)
    except Exception as e:
        logging.error(f"remove_first_segment failed: {e}")
        return df

def remove_last_segment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove the last segment from the DataFrame.

    Args:
        df (pd.DataFrame): DataFrame containing segment data.

    Returns:
        pd.DataFrame: Updated DataFrame with last row removed.
    """
    try:
        return df.iloc[:-1].reset_index(drop=True)
    except Exception as e:
        logging.error(f"remove_last_segment failed: {e}")
        return df

