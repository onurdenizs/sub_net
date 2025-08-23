# utils/platform_ops.py
# -*- coding: utf-8 -*-
"""Platform and station helper utilities.

This module provides:
- Basic platform/track stats extracted from SBB datasets
- Station connectivity and entry-node detection
- Platform→track conversion helpers (for Stage 02)
- Robust JSON/coord parsing and length-aware polyline interpolation

All public functions use English names and Google-style docstrings.
"""

from __future__ import annotations

import ast
import json
import logging
import math
import re
import statistics
from typing import Dict, List, Optional, Tuple

import numpy as np
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

# -----------------------------------------------------------------------------
# Column name constants (to avoid typos)
# -----------------------------------------------------------------------------
COL_LINE = "Line"
COL_LINIE = "Linie"
COL_KM = "KM"
COL_STATION = "Station abbreviation"
COL_PLATFORM_NUM = "Platform number"
COL_PLATFORM_TYPE = "Platform type"
COL_PLATFORM_LEN = "Platform length"
COL_EDGE_LEN = "Length of platform edge"
COL_COORD1 = "1_coord"
COL_COORD2 = "2_coord"
COL_FID = "FID"
COL_GEO_SHAPE = "Geo shape"
COL_START_OP = "START_OP"
COL_END_OP = "END_OP"

# Module logger
logger = logging.getLogger(__name__)


# =============================================================================
# General helpers
# =============================================================================
def find_direction_between_coordinates(coord1: List[float], coord2: List[float]) -> str:
    """Classify whether coord2 is East or West relative to coord1 (EPSG:2056).

    It compares X coordinates. This is a coarse heuristic sufficient for
    building "West/East" buckets for station-approach logic.

    Args:
      coord1: [X1, Y1].
      coord2: [X2, Y2].

    Returns:
      "East", "West", or "Same".
    """
    x1 = coord1[0]
    x2 = coord2[0]
    if x2 > x1:
        return "East"
    if x2 < x1:
        return "West"
    return "Same"


def _safe_json_or_literal(raw: object) -> object:
    """Parse a string that may be JSON-like or Python-literal-like.

    Args:
      raw: Input value (string/list).

    Returns:
      Parsed Python object (list/dict/...) or the original value if already parsed.
    """
    if isinstance(raw, (list, dict)):
        return raw
    s = str(raw)
    try:
        return json.loads(s.replace("'", '"'))
    except Exception:
        try:
            return ast.literal_eval(s)
        except Exception:
            return s


def _parse_coords_field(raw: object) -> List[List[float]]:
    """Parse coordinates stored as a JSON/list-like string or already a list.

    Args:
      raw: Value of a coordinate field.

    Returns:
      List of [x, y] pairs. Returns [] if parsing fails.
    """
    obj = _safe_json_or_literal(raw)
    if isinstance(obj, list) and all(
        isinstance(c, (list, tuple)) and len(c) >= 2 for c in obj
    ):
        return [[float(c[0]), float(c[1])] for c in obj]
    # Some flows store dict {"type": "LineString", "coordinates": [...]}
    if isinstance(obj, dict) and "coordinates" in obj:
        coords = obj["coordinates"]
        if isinstance(coords, list) and all(
            isinstance(c, (list, tuple)) and len(c) >= 2 for c in coords
        ):
            return [[float(c[0]), float(c[1])] for c in coords]
    return []


def _polyline_length(coords: List[List[float]]) -> float:
    """Compute total polyline length in meters (EPSG:2056)."""
    if len(coords) < 2:
        return 0.0
    total = 0.0
    for i in range(len(coords) - 1):
        dx = coords[i + 1][0] - coords[i][0]
        dy = coords[i + 1][1] - coords[i][1]
        total += math.hypot(dx, dy)
    return total


def _interpolate_along_polyline(
    coords: List[List[float]], distance_m: float
) -> List[float]:
    """Interpolate a point at the given distance along a polyline.

    Args:
      coords: List of [x, y].
      distance_m: Distance from the start (>=0). If distance exceeds total length,
        the last coordinate is returned.

    Returns:
      [x, y] coordinate at the requested arclength position.
    """
    if not coords:
        return []
    if distance_m <= 0:
        return [coords[0][0], coords[0][1]]

    # Walk segments
    remaining = distance_m
    for i in range(len(coords) - 1):
        x0, y0 = coords[i]
        x1, y1 = coords[i + 1]
        seg_len = math.hypot(x1 - x0, y1 - y0)
        if seg_len <= 0:
            continue
        if remaining <= seg_len:
            t = remaining / seg_len  # 0..1
            return [x0 + t * (x1 - x0), y0 + t * (y1 - y0)]
        remaining -= seg_len
    # If we got here, distance beyond end -> return last point
    return [coords[-1][0], coords[-1][1]]


# =============================================================================
# Platform filtering and basic lengths (legacy Stage 02 flow)
# =============================================================================
def filter_perron_data(perron_df: pd.DataFrame, unique_ops: set) -> pd.DataFrame:
    """Filter perronkante/perron rows to relevant station set."""
    return perron_df[perron_df[COL_STATION].isin(unique_ops)].copy()


def get_station_tracks(current_station_perron_df: pd.DataFrame) -> set:
    """Get unique platform numbers for the current station."""
    return set(current_station_perron_df[COL_PLATFORM_NUM].dropna().unique())


def calculate_platform_lengths(
    current_station_perron_df: pd.DataFrame, station_code: str, lg: logging.Logger
) -> Tuple[Optional[float], Optional[float], Optional[float], int]:
    """Aggregate per-platform lengths using perronkante 'edge' lengths.

    Args:
      current_station_perron_df: Rows for a single station (perronkante).
      station_code: Station abbreviation.
      lg: Logger.

    Returns:
      (min_len, max_len, avg_len, platform_count) in meters.
      If no valid lengths exist, returns (None, None, None, 0).
    """
    unique_tracks = get_station_tracks(current_station_perron_df)
    track_lengths: List[float] = []
    for track in unique_tracks:
        mask = current_station_perron_df[COL_PLATFORM_NUM] == track
        lengths = pd.to_numeric(
            current_station_perron_df.loc[mask, COL_EDGE_LEN], errors="coerce"
        )
        val = lengths.sum()
        if pd.notna(val) and val > 0:
            track_lengths.append(float(val))

    if track_lengths:
        min_len = min(track_lengths)
        max_len = max(track_lengths)
        avg_len = statistics.mean(track_lengths)
        lg.debug(
            "%s platform-lengths (m): min=%.2f, max=%.2f, avg=%.2f",
            station_code,
            min_len,
            max_len,
            avg_len,
        )
        return min_len, max_len, avg_len, len(unique_tracks)
    lg.warning("⚠️ Station %s has no valid platform length info.", station_code)
    return None, None, None, 0


def decide_platform_length(
    min_len: Optional[float], max_len: Optional[float], avg_len: Optional[float]
) -> float:
    """Pick a 'decided' platform length based on policy and clamp to bounds."""
    if min_len is None or max_len is None or avg_len is None:
        return float(DEFAULT_PLATFORM_LENGTH)
    if PLATFORM_LENGTH_DECISION_METHOD == "X":
        chosen = max_len
    elif PLATFORM_LENGTH_DECISION_METHOD == "N":
        chosen = min_len
    elif PLATFORM_LENGTH_DECISION_METHOD == "A":
        chosen = avg_len
    else:
        return float(DEFAULT_PLATFORM_LENGTH)
    return float(max(MIN_PLATFORM_LENGTH, min(MAX_PLATFORM_LENGTH, chosen)))


def get_fallback_values() -> Tuple[float, int]:
    """Fallback platform length and count when data is missing."""
    length = {
        "X": MAX_PLATFORM_LENGTH,
        "N": MIN_PLATFORM_LENGTH,
    }.get(FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH, DEFAULT_PLATFORM_LENGTH)

    count = {
        "X": MAX_PLATFORM_COUNT,
        "N": MIN_PLATFORM_COUNT,
    }.get(FILL_EMPTY_PLATFORM_NO_DATA_WITH, DEFAULT_PLATFORM_COUNT)

    return float(length), int(count)


def build_station_info(
    polygon_df: pd.DataFrame, perron_df: pd.DataFrame, lg: logging.Logger
) -> pd.DataFrame:
    """Build base station info using perronkante lengths (legacy Stage 02 logic)."""
    unique_ops = set(polygon_df[COL_START_OP]).union(polygon_df[COL_END_OP])

    # Collect line ids per station
    station_line_map = (
        polygon_df[[COL_START_OP, COL_END_OP, COL_LINIE]]
        .melt(id_vars=[COL_LINIE], value_name="station")[["station", COL_LINIE]]
        .drop_duplicates()
        .groupby("station")[COL_LINIE]
        .apply(list)
        .to_dict()
    )

    processed_rows: List[Dict] = []
    for idx, op in enumerate(unique_ops, 1):
        lg.info("📊 Station %d/%d: %s", idx, len(unique_ops), op)
        current = perron_df[perron_df[COL_STATION] == op]

        if current.empty:
            platform_length, platform_count = get_fallback_values()
            min_len = max_len = avg_len = platform_length
        else:
            min_len, max_len, avg_len, platform_count = calculate_platform_lengths(
                current, op, lg
            )
            if min_len is None:
                platform_length, platform_count = get_fallback_values()
                min_len = max_len = avg_len = platform_length
            else:
                platform_length = decide_platform_length(min_len, max_len, avg_len)
                platform_count = max(
                    MIN_PLATFORM_COUNT, min(MAX_PLATFORM_COUNT, platform_count)
                )

        result = {
            "station": op,
            "minimum_platform_length": min_len,
            "maximum_platform_length": max_len,
            "average_platform_length": avg_len,
            "decided_platform_length": platform_length,
            "platform_count": platform_count,
            "line_ids": station_line_map.get(op, []),
        }
        processed_rows.append(result)

    df = pd.DataFrame(processed_rows).sort_values(by="station").reset_index(drop=True)
    return df


# =============================================================================
# Station connections and entry-node detection
# =============================================================================
def find_station_connections(
    platform_df: pd.DataFrame, polygon_df: pd.DataFrame, lg: logging.Logger
) -> pd.DataFrame:
    """Determine connected stations and their directions (West/East).

    For each filtered line segment in polygon_df:
      - Determine direction by comparing first two / last two points (EPSG:2056 X-axis).
      - Update `connected_stations` sets accordingly.

    Args:
      platform_df: DataFrame with a 'station' column.
      polygon_df: Filtered sub-network segments with columns START_OP, END_OP, Geo shape.
      lg: Logger.

    Returns:
      platform_df with a new 'connected_stations' column:
        {'West': set(...), 'East': set(...)}
    """
    platform_df["connected_stations"] = platform_df.apply(
        lambda _: {"West": set(), "East": set()}, axis=1
    )

    for _, row in polygon_df.iterrows():
        start_op = row[COL_START_OP]
        end_op = row[COL_END_OP]
        coords = parse_geo_shape(row[COL_GEO_SHAPE])

        if not coords or len(coords) < 2:
            lg.warning(
                "⚠️ Segment %s-%s has insufficient coordinates.", start_op, end_op
            )
            continue

        dir_start_to_end = find_direction_between_coordinates(coords[0], coords[1])
        dir_end_to_start = find_direction_between_coordinates(coords[-1], coords[-2])

        # Update start_op
        idx_s = platform_df[platform_df["station"] == start_op].index
        if not idx_s.empty and dir_start_to_end in {"West", "East"}:
            platform_df.at[idx_s[0], "connected_stations"][dir_start_to_end].add(end_op)

        # Update end_op
        idx_e = platform_df[platform_df["station"] == end_op].index
        if not idx_e.empty and dir_end_to_start in {"West", "East"}:
            platform_df.at[idx_e[0], "connected_stations"][dir_end_to_start].add(
                start_op
            )

    platform_df.sort_values(by="station", inplace=True)
    platform_df.reset_index(drop=True, inplace=True)
    return platform_df


def define_station_types(platform_df: pd.DataFrame) -> pd.DataFrame:
    """Label stations as 'two-way' / 'single-direction' / 'isolated' based on connections."""

    def _label(conn: Dict[str, set]) -> str:
        if conn["West"] and conn["East"]:
            return "two-way"
        if conn["West"] or conn["East"]:
            return "single-direction"
        return "isolated"

    platform_df["type"] = platform_df["connected_stations"].apply(_label)
    platform_df.sort_values(by="station", inplace=True)
    platform_df.reset_index(drop=True, inplace=True)
    return platform_df


def find_entry_nodes(
    platform_df: pd.DataFrame, polygon_df: pd.DataFrame, lg: logging.Logger
) -> pd.DataFrame:
    """Compute station entry nodes along approach segments (distance-aware).

    For each neighbor station on West/East sets, find the corresponding segment
    (station->neighbor or neighbor->station), then compute an entry point located at:
        ENTRY_OFFSET_BUFFER + decided_platform_length / 2   meters
    away from the station, along the segment polyline.

    The function creates a list of dicts in 'entry_nodes', e.g.:
      {"Direction": "West", "Connected Station": "XYZ", "Line": 100, "Coordinates": [x,y]}

    Notes:
      - Robust to string/JSON '_coordinates' storage.
      - Falls back to warning if segment too short for entry offset.

    Args:
      platform_df: DataFrame with 'station', 'decided_platform_length', 'connected_stations'.
      polygon_df: Filtered sub-network with columns including:
                  START_OP, END_OP, Linie, Geo shape, _coordinates (stringified).
      lg: Logger.

    Returns:
      platform_df with a filled 'entry_nodes' column (list).
    """
    platform_df["entry_nodes"] = platform_df.apply(lambda _: [], axis=1)

    for idx, row in platform_df.iterrows():
        station = row["station"]
        L = float(row["decided_platform_length"])
        entry_offset = float(ENTRY_OFFSET_BUFFER) + 0.5 * L
        conn = row["connected_stations"]

        for direction in ("West", "East"):
            neighbors = list(conn.get(direction, []))
            if not neighbors:
                continue

            for nb in neighbors:
                # Try segment station -> nb
                seg_start = polygon_df[
                    (polygon_df[COL_START_OP] == station)
                    & (polygon_df[COL_END_OP] == nb)
                ]
                # Or reverse nb -> station
                seg_end = polygon_df[
                    (polygon_df[COL_END_OP] == station)
                    & (polygon_df[COL_START_OP] == nb)
                ]

                segment_df = None
                from_start = True
                if not seg_start.empty:
                    if len(seg_start) > 1:
                        lg.warning(
                            "Multiple segments found %s→%s; using the first.",
                            station,
                            nb,
                        )
                    segment_df = seg_start.iloc[0]
                    from_start = True
                elif not seg_end.empty:
                    if len(seg_end) > 1:
                        lg.warning(
                            "Multiple segments found %s→%s; using the first.",
                            nb,
                            station,
                        )
                    segment_df = seg_end.iloc[0]
                    from_start = False
                else:
                    lg.warning(
                        "No segment found between %s and %s; skipping entry.",
                        station,
                        nb,
                    )
                    continue

                try:
                    line_id = int(segment_df[COL_LINIE])
                except Exception:
                    line_id = None

                # Pull coordinates robustly: prefer '_coordinates' if present, else parse Geo shape
                coords_raw = segment_df.get("_coordinates", None)
                coords = (
                    _parse_coords_field(coords_raw)
                    if coords_raw is not None
                    else parse_geo_shape(segment_df[COL_GEO_SHAPE])
                )
                if len(coords) < 2:
                    lg.warning(
                        "Segment %s-%s lacks usable coordinates; skipping.", station, nb
                    )
                    continue

                total_len = _polyline_length(coords)
                if entry_offset >= total_len:
                    lg.warning(
                        "Segment %s-%s (Line %s) len=%.1f m < entry offset=%.1f m; cannot place entry.",
                        station,
                        nb,
                        line_id if line_id is not None else "?",
                        total_len,
                        entry_offset,
                    )
                    continue

                if from_start:
                    pt = _interpolate_along_polyline(coords, entry_offset)
                else:
                    # from the end: mirror by using (total_len - entry_offset)
                    pt = _interpolate_along_polyline(
                        coords, max(0.0, total_len - entry_offset)
                    )

                entry_node = {
                    "Direction": direction,
                    "Connected Station": nb,
                    "Line": line_id,
                    "Coordinates": pt,
                }
                platform_df.at[idx, "entry_nodes"].append(entry_node)

        # Ensure deterministic order for reproducibility
        platform_df.at[idx, "entry_nodes"] = sorted(
            platform_df.at[idx, "entry_nodes"],
            key=lambda d: (d.get("Direction", ""), d.get("Connected Station", "")),
        )

    platform_df.sort_values(by="station", inplace=True)
    platform_df.reset_index(drop=True, inplace=True)
    return platform_df


# =============================================================================
# NEW: Platform→track stats for Stage 02 patch (hybrid layout pipeline)
# =============================================================================
def _safe_numeric(series: pd.Series) -> pd.Series:
    """Convert a Series to numeric (meters), coercing errors to NaN."""
    return pd.to_numeric(series, errors="coerce")


def _drop_near_duplicate_edges(df: pd.DataFrame, tol_m: float = 5.0) -> pd.DataFrame:
    """Drop near-duplicate perronkante rows by FID or close midpoints.

    Args:
      df: Candidate rows for a single station.
      tol_m: Midpoint-distance tolerance in meters.

    Returns:
      Deduplicated DataFrame.
    """
    copy = df.copy()
    # Prefer unique FID if present
    if COL_FID in copy.columns:
        copy = copy.sort_values(COL_FID).drop_duplicates(subset=[COL_FID], keep="first")

    def _midpoint(row) -> Optional[Tuple[float, float]]:
        try:
            x1, y1 = [float(v.strip()) for v in str(row[COL_COORD1]).split(",")]
            x2, y2 = [float(v.strip()) for v in str(row[COL_COORD2]).split(",")]
            return (0.5 * (x1 + x2), 0.5 * (y1 + y2))
        except Exception:
            return None

    mids = copy.apply(_midpoint, axis=1)
    keep_idx: List[int] = []
    seen: List[Tuple[float, float]] = []
    for idx, mp in mids.items():
        if mp is None:
            keep_idx.append(idx)
            continue
        too_close = any(
            (abs(mp[0] - s[0]) ** 2 + abs(mp[1] - s[1]) ** 2) ** 0.5 < tol_m
            for s in seen
        )
        if not too_close:
            keep_idx.append(idx)
            seen.append(mp)
    return copy.loc[keep_idx]


def normalize_platform_id(p_nr: object) -> Optional[str]:
    """Normalize a platform label into a canonical platform id.

    Collapses edge-side variants into a single id:
      "1/0", "1-1", "1A" -> "1"; single letters remain ("A").
      Empty/NaN returns None.

    Args:
      p_nr: Raw platform label (any type coming from CSV).

    Returns:
      Canonical platform id (string) or None if not parseable.
    """
    if p_nr is None or (isinstance(p_nr, float) and math.isnan(p_nr)):
        return None
    s = str(p_nr).strip().upper()
    if not s or s in {"NAN", "NULL"}:
        return None
    m = re.match(r"^(\d+|[A-Z])", s)
    if not m:
        return None
    token = m.group(1)
    return str(int(token)) if token.isdigit() else token


def gather_platform_stats_for_station(
    station_code: str,
    ober_df: Optional[pd.DataFrame],
    perron_df: Optional[pd.DataFrame],
    kante_df: Optional[pd.DataFrame],
    lg: logging.Logger,
) -> Dict:
    """Aggregate platform stats for a station from multiple sources (best-first).

    Priority: perronoberflache -> perron -> perronkante (fallback).
    For 'kante', multiple edge rows may represent the same platform; we normalize ids
    and estimate platform length from edge lengths (max per platform).

    Args:
      station_code: Station abbreviation (e.g., "OL").
      ober_df: perronoberflache DataFrame or None.
      perron_df: perron DataFrame or None.
      kante_df: perronkante DataFrame or None.
      lg: Logger.

    Returns:
      Dict with:
        platform_ids: List[str]
        platform_lengths: Dict[str, float]
        perron_types: Dict[str, Optional[str]]
        source_used: 'oberflache'|'perron'|'kante'|'default'
        confidence: 'high'|'medium'|'low'
    """

    def _from(df: Optional[pd.DataFrame], source_name: str) -> Optional[Dict]:
        if df is None or df.empty or COL_STATION not in df.columns:
            return None
        sdf = df[df[COL_STATION] == station_code].copy()
        if sdf.empty:
            return None

        # Normalize platform id
        sdf["platform_id"] = sdf.get(COL_PLATFORM_NUM).apply(normalize_platform_id)

        # Length column name may differ by source
        length_col = None
        if COL_PLATFORM_LEN in sdf.columns:
            length_col = COL_PLATFORM_LEN
        elif COL_EDGE_LEN in sdf.columns:
            length_col = COL_EDGE_LEN

        if length_col is None:
            return None

        sdf["length_m"] = _safe_numeric(sdf[length_col])
        sdf = sdf[~sdf["length_m"].isna()]
        if sdf.empty:
            return None

        # kante has many duplicate edges; collapse near-dupes first
        if source_name == "kante":
            try:
                sdf = _drop_near_duplicate_edges(sdf, tol_m=5.0)
            except Exception as ex:
                lg.warning("kante dedup failed for %s: %s", station_code, ex)

        with_id = sdf[~sdf["platform_id"].isna()].copy()
        lengths_by_id: Dict[str, float] = {}
        types_by_id: Dict[str, Optional[str]] = {}

        if not with_id.empty:
            for pid, grp in with_id.groupby("platform_id"):
                # robust choice: take max length to guard partial edges
                lengths_by_id[pid] = float(np.nanmax(grp["length_m"].values))
                if (
                    COL_PLATFORM_TYPE in grp.columns
                    and not grp[COL_PLATFORM_TYPE].dropna().empty
                ):
                    types_by_id[pid] = (
                        grp[COL_PLATFORM_TYPE].dropna().astype(str).str.strip().iloc[0]
                    )
                else:
                    types_by_id[pid] = None

        platform_ids: List[str] = list(lengths_by_id.keys())
        if not platform_ids:
            # As a last resort: cluster by midpoints and assign pseudo ids
            if COL_COORD1 in sdf.columns and COL_COORD2 in sdf.columns:
                sdf = _drop_near_duplicate_edges(sdf, tol_m=8.0).reset_index(drop=True)
                platform_ids = [f"P{i+1}" for i in range(len(sdf))]
                for pid, (_, row) in zip(platform_ids, sdf.iterrows()):
                    lengths_by_id[pid] = float(row["length_m"])
                    if COL_PLATFORM_TYPE in sdf.columns and isinstance(
                        row.get(COL_PLATFORM_TYPE), str
                    ):
                        types_by_id[pid] = row[COL_PLATFORM_TYPE].strip()
                    else:
                        types_by_id[pid] = None

        if not platform_ids:
            return None

        conf = "high" if source_name in {"oberflache", "perron"} else "medium"
        return {
            "platform_ids": platform_ids,
            "platform_lengths": lengths_by_id,
            "perron_types": types_by_id,
            "source_used": source_name,
            "confidence": conf,
        }

    for src_name, df in (
        ("oberflache", ober_df),
        ("perron", perron_df),
        ("kante", kante_df),
    ):
        try:
            res = _from(df, src_name)
            if res:
                return res
        except Exception as ex:
            lg.warning(
                "platform stats via %s failed for %s: %s", src_name, station_code, ex
            )

    lg.info("No platform data for station %s; falling back to defaults.", station_code)
    return {
        "platform_ids": [],
        "platform_lengths": {},
        "perron_types": {},
        "source_used": "default",
        "confidence": "low",
    }


def tracks_from_platforms(perron_types: Dict[str, Optional[str]]) -> int:
    """Compute track count implied by platform types.

    Mittelperron (island) -> 2 tracks; Haus/Aussen -> 1 track; unknown -> 1.

    Args:
      perron_types: Map platform_id -> platform type.

    Returns:
      Track count (integer >= 0).
    """
    count = 0
    for _pid, ptype in perron_types.items():
        p = (ptype or "").strip().lower()
        if "mittel" in p:
            count += 2
        else:
            count += 1
    return count


def decide_track_count(
    tracks_from_platforms_val: int, approach_min_tracks: int, add_bypass: bool
) -> int:
    """Finalize station track count (excluding bypass).

    The final track count should not be less than the number of approach corridors
    (west/east entry clusters) and not less than 1.

    Args:
      tracks_from_platforms_val: Track count derived from platform types.
      approach_min_tracks: Lower bound based on entry topology (>=1).
      add_bypass: Whether bypass will be added as a separate, non-platform track.

    Returns:
      Final track count (bypass excluded).
    """
    base = max(int(tracks_from_platforms_val), int(approach_min_tracks), 1)
    return base
