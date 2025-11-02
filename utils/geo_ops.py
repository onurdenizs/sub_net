# -*- coding: utf-8 -*-
"""
Geometry helpers for station layout synthesis.

This module provides small, composable primitives you can use in Stage-03 and
beyond to:
  - infer a principal axis (E–W vs N–S) from approach geometries,
  - compare/sort points by cardinal direction,
  - compute axis-aligned and Euclidean distances,
  - evaluate points along a line/segment (by parameter or by metric distance),
  - slice polylines by distance,
  - estimate local tangents on approach polylines,
  - generate smooth entry→target connectors using cubic Bézier curves,
  - assemble GeoJSON geometries.

All functions are CRS-agnostic but **assume a projected, metric CRS** for any
distance-based computation (e.g., EPSG:2056 / EPSG:3857). If your inputs are
WGS84 (EPSG:4326), reproject first.

Example
-------
>>> u, angle, label = principal_axis([[0,0],[10,1],[20,0]])
>>> label
'E-W'
>>> p = point_on_line_by_distance([0,0],[10,0], 3.5)
>>> round(p[0], 1)
3.5
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #

logger = logging.getLogger(__name__)
# Do not set a hard level here; let the application/pipeline decide.
# If nobody configures logging, fall back to a simple console handler once.
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(_h)


# --------------------------------------------------------------------------- #
# Data containers
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AxisInfo:
    """Principal axis description.

    Attributes:
        unit (Tuple[float, float]): Unit direction vector (ux, uy).
        angle_deg (float): Angle in degrees, atan2(uy, ux) in [-180, 180].
        label (str): Coarse orientation, one of {"E-W", "N-S"}.
    """

    unit: Tuple[float, float]
    angle_deg: float
    label: str


# --------------------------------------------------------------------------- #
# Internal utilities
# --------------------------------------------------------------------------- #


def _as_array2(coords: Sequence[Sequence[float]]) -> np.ndarray:
    """Validate and coerce coordinates to an (N,2) float array.

    Args:
        coords: Iterable of (x, y) pairs.

    Returns:
        np.ndarray: Array of shape (N, 2).

    Raises:
        ValueError: If input is malformed or has < 2 points.
    """
    try:
        arr = np.asarray(coords, dtype=float)
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"Cannot convert to float array: {exc}") from exc
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise ValueError(f"Expected shape (N,2), got {arr.shape}")
    if arr.shape[0] < 2:
        raise ValueError("At least two points are required.")
    return arr


def _unit(v: np.ndarray) -> np.ndarray:
    """Return unit vector; zero vector is returned unchanged."""
    n = float(np.linalg.norm(v))
    return v / n if n > 0.0 else v


# --------------------------------------------------------------------------- #
# Axis inference & orientation helpers
# --------------------------------------------------------------------------- #


def principal_axis(coords: Sequence[Sequence[float]]) -> AxisInfo:
    """Compute the principal axis of a point set using SVD/PCA.

    The first principal component is used as the axis direction. The function
    also derives a coarse cardinal label ("E-W" vs "N-S") by comparing |ux| and
    |uy| of the unit axis vector.

    Args:
        coords: Iterable of (x, y) points (≥ 2).

    Returns:
        AxisInfo: Unit axis vector, angle (deg), and label.

    Raises:
        ValueError: If coords are invalid.
    """
    pts = _as_array2(coords)
    # Center, compute PCA via SVD
    try:
        _, _, vh = np.linalg.svd(pts - pts.mean(axis=0), full_matrices=False)
        axis = _unit(vh[0])
    except Exception as exc:  # pragma: no cover
        logger.error("SVD failed: %s", exc)
        raise

    angle = math.degrees(math.atan2(axis[1], axis[0]))
    label = "E-W" if abs(axis[0]) >= abs(axis[1]) else "N-S"
    return AxisInfo(
        unit=(float(axis[0]), float(axis[1])), angle_deg=float(angle), label=label
    )


def compare_west_east(a: Sequence[float], b: Sequence[float]) -> int:
    """Compare two points along the X axis (west/east).

    Args:
        a: (x, y) of point A.
        b: (x, y) of point B.

    Returns:
        int: -1 if A is west of B, +1 if east, 0 if same meridian.
    """
    ax, _ = a
    bx, _ = b
    return -1 if ax < bx else (1 if ax > bx else 0)


def compare_south_north(a: Sequence[float], b: Sequence[float]) -> int:
    """Compare two points along the Y axis (south/north).

    Args:
        a: (x, y) of point A.
        b: (x, y) of point B.

    Returns:
        int: -1 if A is south of B, +1 if north, 0 if same parallel.
    """
    _, ay = a
    _, by = b
    return -1 if ay < by else (1 if ay > by else 0)


def axis_aligned_distances(a: Sequence[float], b: Sequence[float]) -> Dict[str, float]:
    """Return axis-aligned and Euclidean distances between two points.

    Args:
        a: (x, y) of point A.
        b: (x, y) of point B.

    Returns:
        dict: {"east_west": |dx|, "north_south": |dy|, "euclid": hypot(dx, dy)}.
    """
    dx = float(b[0] - a[0])
    dy = float(b[1] - a[1])
    return {
        "east_west": abs(dx),
        "north_south": abs(dy),
        "euclid": math.hypot(dx, dy),
    }


# --------------------------------------------------------------------------- #
# Points along lines & line slicing
# --------------------------------------------------------------------------- #


def point_on_line_param(
    p0: Sequence[float], p1: Sequence[float], t: float
) -> List[float]:
    """Evaluate the point P(t) = p0 + t * (p1 - p0).

    Args:
        p0: Start point (x, y).
        p1: End point (x, y).
        t: Parameter value. t∈[0,1] is on the segment; t<0 or t>1 extrapolates.

    Returns:
        [x, y]: Point coordinates.
    """
    p0v = np.asarray(p0, dtype=float)
    p1v = np.asarray(p1, dtype=float)
    pt = p0v + float(t) * (p1v - p0v)
    return [float(pt[0]), float(pt[1])]


def point_on_line_by_distance(
    p0: Sequence[float], p1: Sequence[float], dist_from_p0: float
) -> List[float]:
    """Return a point at a metric distance from p0 toward p1 (extrapolates).

    Args:
        p0: Start point (x, y).
        p1: End point (x, y).
        dist_from_p0: Distance in the same units as coordinates.

    Returns:
        [x, y]: Point coordinates.
    """
    p0v = np.asarray(p0, dtype=float)
    v = np.asarray(p1, dtype=float) - p0v
    u = _unit(v)
    pt = p0v + u * float(dist_from_p0)
    return [float(pt[0]), float(pt[1])]


def cumulative_lengths(coords: Sequence[Sequence[float]]) -> np.ndarray:
    """Cumulative polyline lengths L[i] from the first vertex to vertex i.

    Args:
        coords: Polyline as (N, 2) coordinates (N ≥ 2).

    Returns:
        np.ndarray: Cumulative distances of length N with L[0] == 0.
    """
    pts = _as_array2(coords)
    seg = np.linalg.norm(pts[1:] - pts[:-1], axis=1)
    L = np.concatenate([[0.0], np.cumsum(seg)])
    return L


def slice_line_by_distance(
    coords: Sequence[Sequence[float]],
    start_dist: float,
    end_dist: float,
) -> List[List[float]]:
    """Extract a polyline slice between two distances along the line.

    This is a robust alternative to shapely.ops.substring and works without
    geometry objects.

    Args:
        coords: Source polyline (N×2).
        start_dist: Start distance (>= 0).
        end_dist: End distance (>= start_dist).

    Returns:
        List[[x, y], ...]: Coordinates of the slice. If the requested range is
        outside the line, it is clamped to [0, total_length].

    Raises:
        ValueError: If inputs are invalid.
    """
    if end_dist < start_dist:
        raise ValueError("end_dist must be >= start_dist")
    pts = _as_array2(coords)
    L = cumulative_lengths(pts)
    total = float(L[-1])
    if total == 0.0:
        return [pts[0].tolist(), pts[-1].tolist()]

    s = max(0.0, float(start_dist))
    e = min(float(end_dist), total)
    if e <= s:
        # Degenerate slice → single point (projected onto the line).
        return [point_on_line_param(pts[0], pts[1], 0.0)]

    out: List[List[float]] = []

    def _interp(i: int, target_dist: float) -> np.ndarray:
        """Interpolate a point within segment i..i+1 at absolute distance."""
        d0, d1 = L[i], L[i + 1]
        t = 0.0 if d1 == d0 else (target_dist - d0) / (d1 - d0)
        return pts[i] + t * (pts[i + 1] - pts[i])

    # Walk and collect
    i0 = int(np.searchsorted(L, s, side="right") - 1)
    i1 = int(np.searchsorted(L, e, side="right") - 1)
    i0 = max(0, min(i0, len(pts) - 2))
    i1 = max(0, min(i1, len(pts) - 2))

    start_pt = _interp(i0, s)
    end_pt = _interp(i1, e)

    out.append(start_pt.tolist())
    # Middle vertices fully inside (s, e)
    for i in range(i0 + 1, i1 + 1):
        out.append(pts[i].tolist())
    out.append(end_pt.tolist())
    return out


# --------------------------------------------------------------------------- #
# Tangents & connectors (cubic Bézier)
# --------------------------------------------------------------------------- #


def local_tangent(
    coords: Sequence[Sequence[float]],
    where: str = "end",
    k: int = 3,
) -> Tuple[float, float]:
    """Estimate a local tangent at the start or end of a polyline.

    Args:
        coords: Polyline coordinates (N×2, N ≥ 2).
        where: "start" or "end".
        k: Number of vertices used for the chord (≥ 2 recommended).

    Returns:
        (ux, uy): Unit tangent vector. If the chord collapses, (0, 0) is returned.

    Raises:
        ValueError: If inputs are invalid.
    """
    pts = _as_array2(coords)
    k = max(2, int(k))
    if where not in {"start", "end"}:
        raise ValueError("where must be 'start' or 'end'")

    a, b = (
        (pts[0], pts[min(k - 1, len(pts) - 1)])
        if where == "start"
        else (pts[max(0, len(pts) - k)], pts[-1])
    )
    u = _unit(b - a)
    return float(u[0]), float(u[1])


def bezier_cubic(
    p0: Sequence[float],
    p1: Sequence[float],
    p2: Sequence[float],
    p3: Sequence[float],
    samples: int = 40,
) -> List[List[float]]:
    """Evaluate a cubic Bézier curve.

    B(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t) t^2 P2 + t^3 P3, t ∈ [0, 1].

    Args:
        p0, p1, p2, p3: Control points (x, y).
        samples: Number of sample points along the curve (>= 2).

    Returns:
        List[[x, y], ...]: Sampled coordinates along the curve.
    """
    if samples < 2:
        raise ValueError("samples must be >= 2")
    P0, P1, P2, P3 = map(lambda q: np.asarray(q, dtype=float), (p0, p1, p2, p3))
    t = np.linspace(0.0, 1.0, int(samples))[:, None]
    pts = (
        ((1 - t) ** 3) * P0
        + 3 * ((1 - t) ** 2) * t * P1
        + 3 * (1 - t) * (t**2) * P2
        + (t**3) * P3
    )
    return pts.tolist()


def smooth_connector(
    entry_point: Sequence[float],
    entry_tangent: Sequence[float],
    target_point: Sequence[float],
    target_tangent: Sequence[float],
    handle_len_entry: float = 40.0,
    handle_len_target: float = 40.0,
    samples: int = 40,
) -> Dict[str, object]:
    """Create a smooth cubic Bézier connector between two points.

    Args:
        entry_point: Start point (x, y).
        entry_tangent: Tangent direction at start (dx, dy). Magnitude ignored.
        target_point: End point (x, y).
        target_tangent: Tangent direction at end (dx, dy). Magnitude ignored.
        handle_len_entry: Control handle length near the entry (meters).
        handle_len_target: Control handle length near the target (meters).
        samples: Number of points to sample along the curve.

    Returns:
        GeoJSON-like mapping: {"type": "LineString", "coordinates": [[x, y], ...]}.
    """
    p0 = np.asarray(entry_point, dtype=float)
    p3 = np.asarray(target_point, dtype=float)
    u0 = _unit(np.asarray(entry_tangent, dtype=float))
    u1 = _unit(np.asarray(target_tangent, dtype=float))
    p1 = p0 + u0 * float(handle_len_entry)
    p2 = p3 - u1 * float(handle_len_target)

    coords = bezier_cubic(p0, p1, p2, p3, samples=samples)
    return {"type": "LineString", "coordinates": coords}


def smooth_connector_from_entry_polyline(
    entry_polyline: Sequence[Sequence[float]],
    target_point: Sequence[float],
    target_axis: Sequence[float],
    handle_len_entry: float = 40.0,
    handle_len_target: float = 40.0,
    samples: int = 40,
) -> Dict[str, object]:
    """Convenience wrapper: build a connector using the approach polyline's tangent.

    Args:
        entry_polyline: Coordinates of the approach polyline (last vertex near station).
        target_point: Desired endpoint on/near platform bundle.
        target_axis: Desired axis direction at the target (dx, dy).
        handle_len_entry: Control handle length near the entry (m).
        handle_len_target: Control handle length near the target (m).
        samples: Number of points sampled on the curve.

    Returns:
        GeoJSON-like LineString mapping.

    Notes:
        - Uses the last vertex of `entry_polyline` as the connector start.
        - Tangent at start is estimated using `local_tangent(..., where="end")`.
    """
    pts = _as_array2(entry_polyline)
    start = pts[-1].tolist()
    tx, ty = local_tangent(pts, where="end", k=3)
    return smooth_connector(
        entry_point=start,
        entry_tangent=(tx, ty),
        target_point=target_point,
        target_tangent=target_axis,
        handle_len_entry=handle_len_entry,
        handle_len_target=handle_len_target,
        samples=samples,
    )


# --------------------------------------------------------------------------- #
# GeoJSON helpers
# --------------------------------------------------------------------------- #


def make_linestring(coords: Sequence[Sequence[float]]) -> Dict[str, object]:
    """Return a minimal GeoJSON LineString mapping (no validation)."""
    return {
        "type": "LineString",
        "coordinates": [[float(x), float(y)] for x, y in coords],
    }


def make_point(xy: Sequence[float]) -> Dict[str, object]:
    """Return a minimal GeoJSON Point mapping."""
    return {"type": "Point", "coordinates": [float(xy[0]), float(xy[1])]}


def parse_geojson_coords(geojson_text: str) -> List[List[float]]:
    """Extract coordinates from a GeoJSON text (LineString/Point only).

    Args:
        geojson_text: A JSON string containing a minimal GeoJSON geometry.

    Returns:
        List of coordinates (for Point: a single [x, y] list).

    Raises:
        ValueError: If the input is not a recognized minimal geometry.
    """
    try:
        gj = json.loads(geojson_text)
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"Invalid JSON: {exc}") from exc

    gtype = (gj.get("type") or "").lower()
    if gtype == "linestring":
        coords = gj.get("coordinates", [])
        _ = _as_array2(coords)  # validate
        return [list(map(float, c)) for c in coords]
    elif gtype == "point":
        coords = gj.get("coordinates", [])
        if not isinstance(coords, (list, tuple)) or len(coords) != 2:
            raise ValueError("Point geometry must have a 2-element 'coordinates'.")
        return [list(map(float, coords))]
    else:
        raise ValueError(f"Unsupported GeoJSON type: {gj.get('type')!r}")


# --------------------------------------------------------------------------- #
# Higher-level helpers (optional building blocks)
# --------------------------------------------------------------------------- #


def axis_from_multiple_segments(
    segments: Sequence[Sequence[Sequence[float]]],
) -> AxisInfo:
    """Infer a station axis from multiple approach segments.

    Concatenates all segment vertices and runs PCA; more robust than a single
    edge, particularly for curvy approaches.

    Args:
        segments: Iterable of polylines (each as (N_i, 2) coordinates).

    Returns:
        AxisInfo: Principal axis over all vertices.

    Raises:
        ValueError: If no valid segment has ≥ 2 points.
    """
    all_pts: List[List[float]] = []
    for seg in segments:
        try:
            arr = _as_array2(seg)
        except ValueError:
            continue
        all_pts.extend(arr.tolist())

    if len(all_pts) < 2:
        raise ValueError("Need at least one valid segment with ≥ 2 points.")

    return principal_axis(all_pts)


def project_point_onto_segment(
    p: Sequence[float], a: Sequence[float], b: Sequence[float]
) -> Tuple[List[float], float]:
    """Orthogonally project a point onto a segment AB.

    Args:
        p: Query point (x, y).
        a: Segment start (x, y).
        b: Segment end (x, y).

    Returns:
        (proj, t): proj is the projected point on the infinite line,
                   t is the clamped segment parameter in [0, 1].
    """
    p, a, b = map(lambda q: np.asarray(q, dtype=float), (p, a, b))
    ab = b - a
    denom = float(np.dot(ab, ab))
    t = 0.0 if denom == 0.0 else float(np.dot(p - a, ab) / denom)
    t_clamped = max(0.0, min(1.0, t))
    proj = a + t_clamped * ab
    return [float(proj[0]), float(proj[1])], t_clamped


__all__ = [
    # containers
    "AxisInfo",
    # axis/orientation
    "principal_axis",
    "compare_west_east",
    "compare_south_north",
    "axis_aligned_distances",
    "axis_from_multiple_segments",
    # line math
    "point_on_line_param",
    "point_on_line_by_distance",
    "cumulative_lengths",
    "slice_line_by_distance",
    "project_point_onto_segment",
    # tangents & connectors
    "local_tangent",
    "bezier_cubic",
    "smooth_connector",
    "smooth_connector_from_entry_polyline",
    # GeoJSON
    "make_linestring",
    "make_point",
    "parse_geojson_coords",
]
