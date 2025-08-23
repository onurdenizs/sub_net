# utils/layout_ops.py
# -*- coding: utf-8 -*-
"""Station layout utilities: throat hub clustering and axis estimation.

This module computes per-station throat hubs by clustering entry nodes on
each side (West/East). It can also derive a station axis vector and a robust
axis line, with single-side fallbacks using local mainline headings or PCA.

All geometry is assumed in EPSG:2056 (meters).
"""

from __future__ import annotations

import ast
import json
import logging
import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

import utils.constants as C

logger = logging.getLogger(__name__)

# -----------------------------
# Safe constants with fallbacks
# -----------------------------
THROAT_HUB_MAX_JOINT_DISTANCE: float = float(
    getattr(C, "THROAT_HUB_MAX_JOINT_DISTANCE", 80.0)
)
THROAT_HUB_OFFSET: float = float(getattr(C, "THROAT_HUB_OFFSET", 0.0))
STATION_AXIS_MIN_LENGTH: float = float(getattr(C, "STATION_AXIS_MIN_LENGTH", 200.0))


# -----------------------------
# Data structures
# -----------------------------
@dataclass
class Hub:
    """Represents a single throat hub cluster."""

    side: str  # "West" or "East"
    center: Tuple[float, float]  # (x, y) EPSG:2056
    members: List[Tuple[float, float]]  # raw entry-node coordinates
    size: int  # number of members


# -----------------------------
# Parsing helpers
# -----------------------------
def _safe_parse_entry_nodes(raw: object) -> List[Dict]:
    """Parse entry_nodes column (JSON-ish string or already a list).

    Args:
        raw: The 'entry_nodes' value from CSV row.

    Returns:
        A list of dicts with at least keys: Direction, Connected Station, Coordinates.
    """
    if isinstance(raw, list):
        return raw
    s = str(raw)
    try:
        return json.loads(s.replace("'", '"'))
    except Exception:
        try:
            return ast.literal_eval(s)
        except Exception:
            return []


# -----------------------------
# Geometry helpers
# -----------------------------
def _euclid(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return math.hypot(dx, dy)


def _barycenter(points: Iterable[Tuple[float, float]]) -> Tuple[float, float]:
    pts = list(points)
    if not pts:
        return (0.0, 0.0)
    arr = np.asarray(pts, dtype=float)
    return (float(arr[:, 0].mean()), float(arr[:, 1].mean()))


def _offset_point(
    p: Tuple[float, float], direction: Tuple[float, float], offset: float
) -> Tuple[float, float]:
    """Move point p along 'direction' (vector) by 'offset' meters."""
    vx, vy = direction
    norm = math.hypot(vx, vy)
    if norm == 0 or offset == 0:
        return p
    ux, uy = vx / norm, vy / norm
    return (p[0] + ux * offset, p[1] + uy * offset)


def _normalize(v: Tuple[float, float]) -> Tuple[float, float]:
    """Return unit vector (or (0,0) if degenerate)."""
    vx, vy = v
    n = math.hypot(vx, vy)
    if n == 0:
        return (0.0, 0.0)
    return (vx / n, vy / n)


# -----------------------------
# PCA / heading helpers
# -----------------------------
def _principal_axis(points: List[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    """Estimate dominant 2D orientation of points via PCA.

    Args:
        points: List of (x,y) coordinates.

    Returns:
        Unit vector along first principal component, or None if insufficient variance.
    """
    if len(points) < 2:
        return None
    arr = np.asarray(points, dtype=float)
    arr = arr - arr.mean(axis=0, keepdims=True)
    cov = np.cov(arr.T)
    try:
        vals, vecs = np.linalg.eigh(cov)  # safe for symmetric cov
    except np.linalg.LinAlgError:
        return None
    # largest eigenvector
    idx = int(np.argmax(vals))
    if float(vals[idx]) <= 1e-9:
        return None
    vx, vy = float(vecs[0, idx]), float(vecs[1, idx])
    return _normalize((vx, vy))


def _segment_heading_for_station(
    station: str, segment_df: Optional[pd.DataFrame]
) -> Optional[Tuple[float, float]]:
    """Infer a local mainline heading around a station from polygon segments.

    Heuristic:
      - Prefer a segment where station is START_OP -> heading = coords[0]→coords[1]
      - Else a segment where station is END_OP   -> heading = coords[-2]→coords[-1]
      - If multiple exist, just take the first non-degenerate.

    Args:
        station: Station code.
        segment_df: DataFrame with columns ['START_OP','END_OP','Geo shape'].

    Returns:
        Unit vector (vx, vy) or None.
    """
    if segment_df is None or segment_df.empty:
        return None

    def _try_row(r, start: bool) -> Optional[Tuple[float, float]]:
        try:
            geo = str(r["Geo shape"])
            geo = geo.replace("'", '"')
            data = json.loads(geo)
            coords = data.get("coordinates") or []
            if not isinstance(coords, list) or len(coords) < 2:
                return None
            if start:
                x1, y1 = coords[0]
                x2, y2 = coords[1]
            else:
                x1, y1 = coords[-2]
                x2, y2 = coords[-1]
            return _normalize((x2 - x1, y2 - y1))
        except Exception:
            return None

    # Try START_OP first
    sub_start = segment_df[segment_df["START_OP"] == station]
    for _, r in sub_start.iterrows():
        v = _try_row(r, start=True)
        if v and v != (0.0, 0.0):
            return v

    # Then END_OP
    sub_end = segment_df[segment_df["END_OP"] == station]
    for _, r in sub_end.iterrows():
        v = _try_row(r, start=False)
        if v and v != (0.0, 0.0):
            return v

    return None


# -----------------------------
# Clustering
# -----------------------------
def _cluster_side_points(
    coords: List[Tuple[float, float]], max_dist: float
) -> List[List[Tuple[float, float]]]:
    """Greedy single-link clustering by maximum intra-cluster distance.

    Args:
        coords: Points to cluster.
        max_dist: Maximum allowed distance (m) to join an existing cluster.

    Returns:
        List of clusters; each cluster is a list of (x, y).
    """
    clusters: List[List[Tuple[float, float]]] = []
    for p in coords:
        placed = False
        # try to insert into an existing cluster if near its barycenter
        for cl in clusters:
            center = _barycenter(cl)
            if _euclid(center, p) <= max_dist:
                cl.append(p)
                placed = True
                break
        if not placed:
            clusters.append([p])
    return clusters


# -----------------------------
# Public API
# -----------------------------
def build_throat_hubs_for_station(row: pd.Series) -> Dict[str, List[Hub]]:
    """Build West/East throat hubs by clustering entry nodes of a station.

    Args:
        row: A row from station_info_master.csv containing at least:
             - 'station'
             - 'entry_nodes' (JSON-ish string or list of dicts with 'Direction' and 'Coordinates')

    Returns:
        Dict with keys 'West' and 'East', each a list of Hub objects.
    """
    station = str(row.get("station", "?"))

    entries = _safe_parse_entry_nodes(row.get("entry_nodes", "[]"))
    west_pts: List[Tuple[float, float]] = []
    east_pts: List[Tuple[float, float]] = []

    for node in entries:
        try:
            side = node.get("Direction")
            x, y = node.get("Coordinates", [None, None])
            if x is None or y is None:
                continue
            p = (float(x), float(y))
            if side == "West":
                west_pts.append(p)
            elif side == "East":
                east_pts.append(p)
        except Exception:
            continue

    result: Dict[str, List[Hub]] = {"West": [], "East": []}

    for side, pts in (("West", west_pts), ("East", east_pts)):
        if not pts:
            continue
        clusters = _cluster_side_points(pts, THROAT_HUB_MAX_JOINT_DISTANCE)
        hubs_side: List[Hub] = []
        for cl in clusters:
            bc = _barycenter(cl)
            # Optional: push hub slightly inward (currently no-op unless offset != 0)
            center = _offset_point(bc, (0.0, 0.0), THROAT_HUB_OFFSET)
            hubs_side.append(Hub(side=side, center=center, members=cl, size=len(cl)))
        result[side] = hubs_side

    if not (result["West"] or result["East"]):
        logger.warning("No entry nodes to cluster for station %s.", station)

    return result


def estimate_station_axis_from_hubs(
    hubs: Dict[str, List[Hub]]
) -> Optional[Tuple[float, float]]:
    """Estimate station axis vector from hub barycenters.

    Returns:
        A vector (vx, vy) from West barycenter to East barycenter, or None if
        one side is missing.
    """
    if not hubs.get("West") or not hubs.get("East"):
        return None
    west_all = [h.center for h in hubs["West"]]
    east_all = [h.center for h in hubs["East"]]
    w_bar = _barycenter(west_all)
    e_bar = _barycenter(east_all)
    return (e_bar[0] - w_bar[0], e_bar[1] - w_bar[1])


def hubs_to_serializable(hubs: Dict[str, List[Hub]]) -> Dict[str, List[Dict]]:
    """Convert hubs dict to JSON-serializable structure."""
    out: Dict[str, List[Dict]] = {"West": [], "East": []}
    for side in ("West", "East"):
        for h in hubs.get(side, []):
            out[side].append(
                {
                    "side": h.side,
                    "center": [h.center[0], h.center[1]],
                    "size": h.size,
                    "members": [[p[0], p[1]] for p in h.members],
                }
            )
    return out


def estimate_station_axis_line_from_hubs(
    station: str,
    hubs: Dict[str, List[Hub]],
    logger: logging.Logger,
    min_axis_length: float = STATION_AXIS_MIN_LENGTH,
    segment_df: Optional[pd.DataFrame] = None,
) -> Optional[Tuple[float, float, float, float]]:
    """Build a robust axis line for a station.

    Strategy:
        - If both West and East hubs present:
            axis = line between side barycenters; if shorter than min length,
            extend symmetrically to reach min length.
        - Else (single-side):
            * try PCA on that side's member points to obtain heading,
            * else try heading from local mainline segment geometries,
            * build a centered line of length `min_axis_length` at the side barycenter.

    Args:
        station: Station code.
        hubs: Dict with 'West'/'East' → List[Hub].
        logger: Logger for diagnostics.
        min_axis_length: Minimal length (m) to enforce.
        segment_df: Optional segments DataFrame (START_OP/END_OP/Geo shape).

    Returns:
        (x1, y1, x2, y2) or None if impossible.
    """
    west = hubs.get("West", [])
    east = hubs.get("East", [])

    # Case A: both sides exist -> connect barycenters
    if west and east:
        w_bar = _barycenter([h.center for h in west])
        e_bar = _barycenter([h.center for h in east])
        vx, vy = e_bar[0] - w_bar[0], e_bar[1] - w_bar[1]
        seg_len = math.hypot(vx, vy)
        if seg_len < 1e-6:
            logger.warning("⚠️ Axis degenerate for %s (two-side vector ~0).", station)
            return None
        # enforce minimal length by extending around the midpoint
        mx, my = (w_bar[0] + e_bar[0]) / 2.0, (w_bar[1] + e_bar[1]) / 2.0
        ux, uy = vx / seg_len, vy / seg_len
        half = max(min_axis_length / 2.0, seg_len / 2.0)
        return (mx - ux * half, my - uy * half, mx + ux * half, my + uy * half)

    # Case B: single-side fallback
    side_name = "West" if west else ("East" if east else None)
    if side_name is None:
        # No hubs at all
        logger.warning("⚠️ No hubs for %s; cannot form axis.", station)
        return None

    side_hubs = west if west else east
    side_points = [p for h in side_hubs for p in h.members]
    c = _barycenter([h.center for h in side_hubs])

    # 1) PCA heading
    heading = _principal_axis(side_points)

    # 2) If still none, try segment-derived heading
    if heading is None:
        heading = _segment_heading_for_station(station, segment_df)

    if heading is None or heading == (0.0, 0.0):
        logger.warning("⚠️ Axis degenerate for %s (single-side vector ~0).", station)
        return None

    ux, uy = heading
    half = max(min_axis_length / 2.0, 1.0)
    return (c[0] - ux * half, c[1] - uy * half, c[0] + ux * half, c[1] + uy * half)
