# -*- coding: utf-8 -*-
"""
Helpers for Stage 03:
- 
"""

# utils/layout_ops.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import ast
import json
import logging
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple, Union

logger = logging.getLogger(__name__)


def _parse_entry_nodes(
    entry_nodes: Union[str, Sequence[dict], dict, None]
) -> List[dict]:
    """Normalize 'entry_nodes' into a list of dictionaries.

    Accepts Python-literal strings (with single quotes), JSON strings, already-parsed
    list[dict] or dict, or None. Filters out non-dict items.

    Args:
        entry_nodes: Raw entry_nodes cell value.

    Returns:
        list[dict]: Items with keys like 'Direction' and 'Line' when available.
    """
    if entry_nodes is None:
        return []

    if isinstance(entry_nodes, list):
        return [d for d in entry_nodes if isinstance(d, dict)]

    if isinstance(entry_nodes, dict):
        return [entry_nodes]

    if isinstance(entry_nodes, str):
        s = entry_nodes.strip()
        if not s:
            return []
        # Try Python literal first (handles single quotes)
        try:
            parsed = ast.literal_eval(s)
        except Exception:
            try:
                parsed = json.loads(s)
            except Exception:
                logger.debug("Failed to parse entry_nodes string: %r", s)
                return []

        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list):
            return [d for d in parsed if isinstance(d, dict)]
        return []

    logger.debug("Unexpected entry_nodes type: %s", type(entry_nodes).__name__)
    return []


def _coerce_line_to_int(line_val: Any) -> int:
    """Coerce a 'Line' value into an int (handles int/float/str like '650' or '650.0')."""
    if isinstance(line_val, int):
        return line_val
    if isinstance(line_val, float):
        return int(round(line_val))
    if isinstance(line_val, str):
        s = line_val.strip()
        if s == "":
            raise ValueError("empty line string")
        try:
            return int(s)
        except ValueError:
            return int(round(float(s)))
    return int(line_val)


def _extract_direction_lines(records: List[dict]) -> Tuple[Set[int], Set[int]]:
    """Extract unique line numbers for West and East from entry_nodes records."""
    west_lines: Set[int] = set()
    east_lines: Set[int] = set()

    for rec in records:
        direction = (
            str(rec.get("Direction") or rec.get("direction") or rec.get("dir") or "")
            .strip()
            .lower()
        )
        line_val = rec.get("Line") or rec.get("line") or rec.get("LINE")
        if line_val is None:
            continue

        try:
            line_int = _coerce_line_to_int(line_val)
        except Exception:
            logger.debug("Skipping uncoercible Line value: %r", line_val)
            continue

        if direction == "west":
            west_lines.add(line_int)
        elif direction == "east":
            east_lines.add(line_int)
        else:
            # Ignore other directions for this decision logic
            pass

    return west_lines, east_lines


def decide_main_station_layout(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Decide the station's main layout type from a dataframe row.

    Decision rules (based on West/East line sets from 'entry_nodes'):
      - through_same_line     : At least one line appears in BOTH West and East.
      - through_line_change   : Exactly one West line and one East line, and they differ.
      - terminus_west_open    : Has West lines only.
      - terminus_east_open    : Has East lines only.
      - junction_Y            : Both sides present, no common lines, multiple lines on exactly one side.
      - junction_complex      : Both sides present, no common lines, multiple lines on both sides.
      - isolated              : Parsed but no West/East lines found.
      - unknown               : entry_nodes missing or unparsable.

    Returns:
        dict with:
          layout_type: str
          main_lines : list[int]  (common lines for through_same_line; else empty)
          west_lines : list[int]
          east_lines : list[int]
          reason     : optional str
    """
    try:
        entry_nodes = row.get("entry_nodes", None)
    except Exception:
        return {
            "layout_type": "unknown",
            "main_lines": [],
            "west_lines": [],
            "east_lines": [],
            "reason": "row is not a mapping",
        }

    records = _parse_entry_nodes(entry_nodes)
    if not records:
        return {
            "layout_type": "unknown",
            "main_lines": [],
            "west_lines": [],
            "east_lines": [],
            "reason": "entry_nodes missing or unparsable",
        }

    west_lines, east_lines = _extract_direction_lines(records)
    nW, nE = len(west_lines), len(east_lines)

    if nW == 0 and nE == 0:
        return {
            "layout_type": "isolated",
            "main_lines": [],
            "west_lines": [],
            "east_lines": [],
            "reason": "no west/east lines",
        }

    if nW > 0 and nE == 0:
        return {
            "layout_type": "terminus_west_open",
            "main_lines": [],
            "west_lines": sorted(west_lines),
            "east_lines": [],
        }

    if nW == 0 and nE > 0:
        return {
            "layout_type": "terminus_east_open",
            "main_lines": [],
            "west_lines": [],
            "east_lines": sorted(east_lines),
        }

    common = west_lines & east_lines
    if common:
        return {
            "layout_type": "through_same_line",
            "main_lines": sorted(common),
            "west_lines": sorted(west_lines),
            "east_lines": sorted(east_lines),
        }

    if nW == 1 and nE == 1:
        return {
            "layout_type": "through_line_change",
            "main_lines": [],
            "west_lines": sorted(west_lines),
            "east_lines": sorted(east_lines),
        }

    layout_type = "junction_Y" if (nW > 1) ^ (nE > 1) else "junction_complex"
    return {
        "layout_type": layout_type,
        "main_lines": [],
        "west_lines": sorted(west_lines),
        "east_lines": sorted(east_lines),
    }
