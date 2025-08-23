# utils/layout_ops.py
# -*- coding: utf-8 -*-
"""Station layout utilities: throat hub clustering and axis estimation.

This module computes per-station throat hubs by clustering entry nodes on
each side (West/East), then derives a station axis vector connecting the
West hub barycenter to the East hub barycenter.

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
            # Optional: push hub slightly inward along average vector towards global mean
            # For now, just apply zero or configured offset along a dummy direction (no-op if 0).
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
