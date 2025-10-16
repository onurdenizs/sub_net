# tools/station_layout_master_info.py
# -*- coding: utf-8 -*-
"""Quick, human-readable summary for station master/layout files.

This utility inspects the key processed artifacts and prints a small report:
- Station helper/master with entry nodes (Stage-02 output)
- Station design master (Stage-03 output)
- Filtered sub-network polygon file (Stage-01 output)

It also writes a text report to PROCESSED_DIR for convenience.

Run:
    python tools/station_layout_master_info.py
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from utils.constants import (
    FILTERED_SUB_NETWORK_POLYGON_FILE,
    PROCESSED_DIR,
    STATION_DESIGN_FILE,
    STATION_HELPER_FILE,
)


def _setup_logger(verbosity: int = 0) -> logging.Logger:
    """Configure a simple console logger.

    Args:
        verbosity: 0=INFO, 1+=DEBUG.

    Returns:
        The configured logger instance.
    """
    logger = logging.getLogger("station_layout_master_info")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbosity > 0 else logging.INFO)
    return logger


def _try_read_csv(path: Path, sep: str = ";") -> Optional[pd.DataFrame]:
    """Read a CSV if it exists; otherwise return None."""
    try:
        if path.exists():
            return pd.read_csv(path, delimiter=sep)
    except Exception:
        # fall back to comma if ; fails
        try:
            return pd.read_csv(path)
        except Exception:
            return None
    return None


def _df_info_line(df: Optional[pd.DataFrame], name: str) -> str:
    """Render a one-line summary for a dataframe."""
    if df is None:
        return f"{name:<30} : MISSING"
    n_rows = len(df)
    n_cols = len(df.columns)
    return f"{name:<30} : {n_rows:>6} rows | {n_cols:>3} cols"


def _maybe_preview_columns(df: Optional[pd.DataFrame], cols: list[str]) -> str:
    """Return a short preview for a subset of columns, if available."""
    if df is None:
        return "  (no preview, file missing)"
    existing = [c for c in cols if c in df.columns]
    if not existing:
        return "  (no preview, columns not found)"
    preview = df[existing].head(5).to_string(index=False)
    # Indent each line for nicer formatting
    indented = "\n".join(f"  {line}" for line in preview.splitlines())
    return indented


def build_report(logger: logging.Logger) -> str:
    """Build a consolidated human-readable report as a string."""
    info_df = _try_read_csv(STATION_HELPER_FILE)
    design_df = _try_read_csv(STATION_DESIGN_FILE)
    seg_df = _try_read_csv(FILTERED_SUB_NETWORK_POLYGON_FILE)

    lines: list[str] = []
    lines.append("── Station Layout — Master / Info Report ──")
    lines.append("")
    lines.append(_df_info_line(info_df, "Stage-02 station_info_master"))
    lines.append(_df_info_line(design_df, "Stage-03 station_design_master"))
    lines.append(_df_info_line(seg_df, "Stage-01 filtered_sub_network"))
    lines.append("")

    # Basic sanity checks
    if info_df is not None:
        missing_cols = [
            c for c in ["station", "entry_nodes"] if c not in info_df.columns
        ]
        if missing_cols:
            lines.append(
                f"WARNING: station_info_master missing columns: {missing_cols}"
            )
        else:
            lines.append("station_info_master key columns OK.")
    else:
        lines.append("WARNING: station_info_master.csv not found.")

    if design_df is not None:
        missing_cols = [
            c
            for c in [
                "station",
                "number_of_tracks",
                "platform_length",
                "ref_x",
                "ref_y",
                "layout_type",
            ]
            if c not in design_df.columns
        ]
        if missing_cols:
            lines.append(
                f"WARNING: station_design_master missing columns: {missing_cols}"
            )
        else:
            lines.append("station_design_master key columns OK.")
    else:
        lines.append("WARNING: station_design_master.csv not found.")

    lines.append("")

    # Optional previews
    lines.append("Preview — station_info_master (station, line_ids, entry_nodes):")
    lines.append(
        _maybe_preview_columns(
            info_df, ["station", "line_ids", "entry_nodes", "connected_stations"]
        )
    )
    lines.append("")
    lines.append(
        "Preview — station_design_master (station, number_of_tracks, platform_length, layout_type):"
    )
    lines.append(
        _maybe_preview_columns(
            design_df,
            [
                "station",
                "number_of_tracks",
                "platform_length",
                "layout_type",
                "ref_x",
                "ref_y",
            ],
        )
    )
    lines.append("")

    # Join
    report = "\n".join(lines)
    logger.debug("Report built.")
    return report


def save_report(report: str, logger: logging.Logger) -> Path:
    """Save the report text into PROCESSED_DIR.

    Args:
        report: Report text.
        logger: Logger.

    Returns:
        The saved file path.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "station_layout_master_info.txt"
    out_path.write_text(report, encoding="utf-8")
    logger.info("Report saved: %s", out_path.resolve())
    return out_path


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Summarize station layout/master inputs."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (use -vv for DEBUG).",
    )
    args = parser.parse_args()
    logger = _setup_logger(args.verbose)

    logger.info("Building station layout/master info report...")
    report = build_report(logger)
    print(report)
    save_report(report, logger)
    logger.info("Done.")


if __name__ == "__main__":
    main()
