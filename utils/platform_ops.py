# -*- coding: utf-8 -*-
"""
Helpers for Stage 02:
- Filter perronkante rows to used stations
- Compute per-station platform length stats & counts
- Build connected-stations map (West/East)
- Decide “decided” platform length using configured policy
- Compute entry nodes along line segments with a distance offset
"""

from __future__ import annotations

import ast
import logging
import statistics
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from utils.constants import (
    DEFAULT_PLATFORM_COUNT,
    DEFAULT_PLATFORM_LENGTH,
    ENTRY_OFFSET_BUFFER,
    FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH,
    FILL_EMPTY_PLATFORM_NO_DATA_WITH,
    MAX_PLATFORM_COUNT,
    MAX_PLATFORM_LENGTH,
    MIN_PLATFORM_COUNT,
    MIN_PLATFORM_LENGTH,
    PLATFORM_LENGTH_DECISION_METHOD,
)
from utils.segment_ops import parse_geo_shape


# ------------------------------------------------------------------------------
# Direction helper (X-axis heuristic)
# ------------------------------------------------------------------------------
def find_direction_between_coordinates(coord1: List[float], coord2: List[float]) -> str:
    """
    Heuristically decide if coord2 is East/West of coord1 using X only.

    Returns: "East", "West", or "Same".
    """
    x1 = coord1[0]
    x2 = coord2[0]
    if x2 > x1:
        return "East"
    elif x2 < x1:
        return "West"
    else:
        return "Same"


# ------------------------------------------------------------------------------
# Perron filters & platform stats
# ------------------------------------------------------------------------------

# NOTE: To estimate *track* count (not platform count), prefer customer-track-like
# identifiers when available; otherwise fall back to "Platform number".
_TRACK_ID_CANDIDATES: List[str] = [
    "Customer track number",
    "Customer track no.",
    "Customer track",
    "Track number",
    "Track No",
    "Track ID",
]
_PLATFORM_FALLBACK_CANDIDATES: List[str] = [
    "Platform number",
]


def _pick_track_id_column(df: pd.DataFrame) -> Optional[str]:
    """
    Pick the column that best represents a physical *track* identifier.
    Preference:
      1) customer/track id columns (true track identity),
      2) fallback to "Platform number" if nothing else exists.
    """
    for col in _TRACK_ID_CANDIDATES:
        if col in df.columns:
            return col
    for col in _PLATFORM_FALLBACK_CANDIDATES:
        if col in df.columns:
            return col
    return None


def filter_perron_data(
    perron_df: pd.DataFrame, allowed_stations: Set[str]
) -> pd.DataFrame:
    """Keep only perron rows whose station abbreviation exists in the network."""
    return perron_df[perron_df["Station abbreviation"].isin(allowed_stations)].copy()


def _get_station_tracks(current_station_perron_df: pd.DataFrame) -> Set:
    """Unique platform numbers for a station.

    (Extended) In practice we want *track* identifiers. We therefore first try to
    use a customer-track-like column; if absent we fall back to "Platform number".
    """
    col = _pick_track_id_column(current_station_perron_df)
    if not col:
        return set()
    # Normalize to string to avoid 1 vs 1.0 mismatches and trim whitespace.
    return set(current_station_perron_df[col].dropna().astype(str).str.strip().unique())


def _group_lengths_by_track(current_station_perron_df: pd.DataFrame) -> List[float]:
    """
    Sum 'Length of platform edge' per *track identifier* and return the list
    of per-track total lengths. Falls back to 'Platform number' if no explicit
    track id column exists.
    """
    col = _pick_track_id_column(current_station_perron_df)
    if not col or "Length of platform edge" not in current_station_perron_df.columns:
        return []
    grouped = (
        current_station_perron_df.dropna(subset=[col, "Length of platform edge"])
        .assign(**{col: current_station_perron_df[col].astype(str).str.strip()})
        .groupby(col)["Length of platform edge"]
        .sum()
    )
    return grouped.values.tolist()


def calculate_platform_lengths(
    current_station_perron_df: pd.DataFrame, op: str, logger: logging.Logger
) -> Tuple[float, float, float, int]:
    """
    Compute min/max/avg platform lengths and platform count for a station.
    Sums lengths per track (platform number).

    (Extended) Track count now uses a *track id* column when available
    (e.g., 'Customer track number'); otherwise it falls back to 'Platform number'.
    Length statistics are computed per chosen track id by summing rows that
    belong to the same track.
    """
    unique_tracks = _get_station_tracks(current_station_perron_df)
    track_lengths = _group_lengths_by_track(current_station_perron_df)

    if track_lengths:
        min_len = min(track_lengths)
        max_len = max(track_lengths)
        avg_len = statistics.mean(track_lengths)
        logger.debug(
            "%s platform lengths (min/max/avg): %.2f / %.2f / %.2f | tracks=%d",
            op,
            min_len,
            max_len,
            avg_len,
            len(unique_tracks),
        )
        return min_len, max_len, avg_len, len(unique_tracks)
    else:
        logger.warning("⚠️ Station %s has no valid platform length info.", op)
        return None, None, None, 0


def decide_platform_length(min_len: float, max_len: float, avg_len: float) -> float:
    """
    Pick a single “decided” platform length per station based on policy, then
    hard-clamp the result into [MIN_PLATFORM_LENGTH, MAX_PLATFORM_LENGTH]:

      X → take max_len
      N → take min_len
      A → take avg_len
      else → DEFAULT_PLATFORM_LENGTH
    """
    if PLATFORM_LENGTH_DECISION_METHOD == "X":
        chosen = max_len
    elif PLATFORM_LENGTH_DECISION_METHOD == "N":
        chosen = min_len
    elif PLATFORM_LENGTH_DECISION_METHOD == "A":
        chosen = avg_len
    else:
        chosen = DEFAULT_PLATFORM_LENGTH

    # Final policy-independent clamp
    return max(MIN_PLATFORM_LENGTH, min(MAX_PLATFORM_LENGTH, chosen))


def _fallback_values() -> Tuple[float, int]:
    """Fallback length & count when no perron info exists for a station."""
    raw_len = {"X": MAX_PLATFORM_LENGTH, "N": MIN_PLATFORM_LENGTH}.get(
        FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH, DEFAULT_PLATFORM_LENGTH
    )
    # Clamp fallback length as well
    length = max(MIN_PLATFORM_LENGTH, min(MAX_PLATFORM_LENGTH, raw_len))

    count = {"X": MAX_PLATFORM_COUNT, "N": MIN_PLATFORM_COUNT}.get(
        FILL_EMPTY_PLATFORM_NO_DATA_WITH, DEFAULT_PLATFORM_COUNT
    )
    return length, count


def build_station_info(
    polygon_df: pd.DataFrame, perron_df: pd.DataFrame, logger: logging.Logger
) -> pd.DataFrame:
    """
    Build a station table with basic platform metrics and line IDs.

    Returns columns:
      - station
      - minimum_platform_length, maximum_platform_length, average_platform_length
      - decided_platform_length
      - platform_count
      - line_ids (list of ints)
    """
    unique_ops: Set[str] = set(polygon_df["START_OP"]).union(polygon_df["END_OP"])

    # Build station → [line_ids] map by melting START_OP/END_OP
    station_line_map: Dict[str, List[int]] = (
        polygon_df[["START_OP", "END_OP", "Linie"]]
        .melt(id_vars=["Linie"], value_name="station")[["station", "Linie"]]
        .drop_duplicates()
        .groupby("station")["Linie"]
        .apply(list)
        .to_dict()
    )

    rows: List[Dict] = []
    for idx, op in enumerate(unique_ops, start=1):
        logger.info("📊 Station %d/%d: %s", idx, len(unique_ops), op)
        per_station = perron_df[perron_df["Station abbreviation"] == op]

        if per_station.empty:
            platform_length, platform_count = _fallback_values()
            min_len = max_len = avg_len = platform_length
        else:
            min_len, max_len, avg_len, platform_count = calculate_platform_lengths(
                per_station, op, logger
            )
            if min_len is None:
                platform_length, platform_count = _fallback_values()
                min_len = max_len = avg_len = platform_length
            else:
                platform_length_raw = decide_platform_length(min_len, max_len, avg_len)
                # Final safety clamp (defensive; decide_platform_length already clamps)
                platform_length = max(
                    MIN_PLATFORM_LENGTH, min(MAX_PLATFORM_LENGTH, platform_length_raw)
                )
                if platform_length != platform_length_raw:
                    logger.debug(
                        "Platform length clamped for %s: %.2f → %.2f (MIN=%d, MAX=%d)",
                        op,
                        platform_length_raw,
                        platform_length,
                        MIN_PLATFORM_LENGTH,
                        MAX_PLATFORM_LENGTH,
                    )
                platform_count = max(
                    MIN_PLATFORM_COUNT, min(MAX_PLATFORM_COUNT, platform_count)
                )

        rows.append(
            {
                "station": op,
                "minimum_platform_length": min_len,
                "maximum_platform_length": max_len,
                "average_platform_length": avg_len,
                "decided_platform_length": platform_length,
                "platform_count": platform_count,
                "line_ids": station_line_map.get(op, []),
            }
        )

    out = pd.DataFrame(rows).sort_values(by="station").reset_index(drop=True)
    return out


# ------------------------------------------------------------------------------
# Connectivity & station type
# ------------------------------------------------------------------------------
def find_station_connections(
    platform_df: pd.DataFrame, polygon_df: pd.DataFrame, logger: logging.Logger
) -> pd.DataFrame:
    """
    Determine connected stations and their directions (West/East)
    based on the filtered polygon segments.

    Adds/returns column:
      - connected_stations: dict {"West": set(), "East": set()}
        (sets are used in-memory; they will be stringified when saved to CSV)
    """
    platform_df["connected_stations"] = platform_df.apply(
        lambda _row: {"West": set(), "East": set()}, axis=1
    )

    for _, seg in polygon_df.iterrows():
        start_op = seg["START_OP"]
        end_op = seg["END_OP"]
        coords = parse_geo_shape(seg["Geo shape"])

        if not coords or len(coords) < 2:
            logger.warning(
                "⚠️ Segment %s-%s has insufficient coordinates.", start_op, end_op
            )
            continue

        # Direction for start → end
        dir_se = find_direction_between_coordinates(coords[0], coords[1])
        # Direction for end → start
        dir_es = find_direction_between_coordinates(coords[-1], coords[-2])

        # Update start_op
        start_idx = platform_df.index[platform_df["station"] == start_op]
        if not start_idx.empty and dir_se in {"West", "East"}:
            platform_df.at[start_idx[0], "connected_stations"][dir_se].add(end_op)

        # Update end_op
        end_idx = platform_df.index[platform_df["station"] == end_op]
        if not end_idx.empty and dir_es in {"West", "East"}:
            platform_df.at[end_idx[0], "connected_stations"][dir_es].add(start_op)

    platform_df.sort_values(by="station", inplace=True)
    platform_df.reset_index(drop=True, inplace=True)
    return platform_df


def define_station_types(platform_df: pd.DataFrame) -> pd.DataFrame:
    """Classify station type using presence of West/East connections."""

    def _classify(conn: Dict[str, Set[str]]) -> str:
        w, e = conn["West"], conn["East"]
        return (
            "two-way" if (w and e) else ("single-direction" if (w or e) else "isolated")
        )

    platform_df["type"] = platform_df["connected_stations"].apply(_classify)
    platform_df.sort_values(by="station", inplace=True)
    platform_df.reset_index(drop=True, inplace=True)
    return platform_df


# ------------------------------------------------------------------------------
# Entry nodes
# ------------------------------------------------------------------------------
def find_entry_nodes(
    platform_df: pd.DataFrame, polygon_df: pd.DataFrame, logger: logging.Logger
) -> pd.DataFrame:
    """
    For each station and each connected neighbor (West/East), place an entry node on
    the corresponding segment at an offset of:
        ENTRY_OFFSET_BUFFER + decided_platform_length / 2
    from the station end.

    Notes:
      - We approximate a per-vertex step by: segment_length / number_of_points.
      - Coordinates are read from Stage-01 output column "_coordinates" (stored as text).
    """
    # Prepare column of mutable lists (in-place append will persist)
    platform_df["entry_nodes"] = platform_df.apply(lambda _row: [], axis=1)

    for idx, row in platform_df.iterrows():
        station = row["station"]
        logger.info(
            "📥 Computing entry nodes for %s (%d/%d)",
            station,
            idx + 1,
            len(platform_df),
        )

        connections = row["connected_stations"]  # {"West": set(...), "East": set(...)}
        for direction, neighbors in connections.items():
            for neighbor in list(neighbors):
                # segments where station is the START
                start_seg = polygon_df[
                    (polygon_df["START_OP"] == station)
                    & (polygon_df["END_OP"] == neighbor)
                ]
                # segments where station is the END
                end_seg = polygon_df[
                    (polygon_df["END_OP"] == station)
                    & (polygon_df["START_OP"] == neighbor)
                ]

                if not start_seg.empty:
                    if len(start_seg) == 1:
                        poly_len = float(start_seg["polygon_length"].iloc[0])
                        npts = int(start_seg["number_of_polygon_points"].iloc[0])
                        line_id = int(start_seg["Linie"].iloc[0])

                        # Approx average spacing between points
                        step = max(1, int(round(poly_len / max(1, npts))))
                        platform_len = int(row["decided_platform_length"])
                        total_offset = int(ENTRY_OFFSET_BUFFER + platform_len / 2)
                        idx_on_line = int(total_offset / step)

                        if idx_on_line >= npts:
                            logger.warning(
                                "⚠️ %s→%s (Linie %s) needs %d points but has %d (start side).",
                                station,
                                neighbor,
                                line_id,
                                idx_on_line,
                                npts,
                            )
                            continue

                        coords_text = start_seg["_coordinates"].iloc[0]
                        coords_list = ast.literal_eval(coords_text)
                        xy = coords_list[idx_on_line]

                        row["entry_nodes"].append(
                            {
                                "Direction": direction,
                                "Connected Station": neighbor,
                                "Line": line_id,
                                "Coordinates": xy,
                            }
                        )
                    else:
                        logger.warning(
                            "⚠️ Multiple start-side segments for %s↔%s; skipping.",
                            station,
                            neighbor,
                        )

                elif not end_seg.empty:
                    if len(end_seg) == 1:
                        poly_len = float(end_seg["polygon_length"].iloc[0])
                        npts = int(end_seg["number_of_polygon_points"].iloc[0])
                        line_id = int(end_seg["Linie"].iloc[0])

                        step = max(1, int(round(poly_len / max(1, npts))))
                        platform_len = int(row["decided_platform_length"])
                        total_offset = int(ENTRY_OFFSET_BUFFER + platform_len / 2)
                        idx_on_line = int(total_offset / step)
                        rev_idx = -idx_on_line  # from the end toward the station

                        if idx_on_line >= npts:
                            logger.warning(
                                "⚠️ %s→%s (Linie %s) needs %d points but has %d (end side).",
                                station,
                                neighbor,
                                line_id,
                                idx_on_line,
                                npts,
                            )
                            continue

                        coords_text = end_seg["_coordinates"].iloc[0]
                        coords_list = ast.literal_eval(coords_text)
                        xy = coords_list[rev_idx]

                        row["entry_nodes"].append(
                            {
                                "Direction": direction,
                                "Connected Station": neighbor,
                                "Line": line_id,
                                "Coordinates": xy,
                            }
                        )
                    else:
                        logger.warning(
                            "⚠️ Multiple end-side segments for %s↔%s; skipping.",
                            station,
                            neighbor,
                        )

                else:
                    logger.warning(
                        "⚠️ No segment found for %s↔%s; skipping.", station, neighbor
                    )

    platform_df.sort_values(by="station", inplace=True)
    platform_df.reset_index(drop=True, inplace=True)
    return platform_df
