#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline launcher for the project.

This script orchestrates sequential execution of individual pipeline stages.
You select which stages to run using the command-line arguments `--start` and
`--end`. Each stage is a module that exposes a `run(debug: bool = False)` entrypoint.

-------------------------------------------------------------------------------
CLI usage examples
-------------------------------------------------------------------------------
# Run only Stage 1
python run_pipeline.py --start 1 --end 1

# Run only Stage 2 with verbose logging enabled inside the stages
python run_pipeline.py --start 2 --end 2 --debug

# Run stages 1..2 (inclusive)
python run_pipeline.py --start 1 --end 2

Notes
- If you request a stage number that is not defined in STAGES, it will be
  skipped with a warning message.
- Stages are executed in increasing order from --start to --end (inclusive).
"""

from __future__ import annotations

import argparse
from typing import Callable, Dict, Tuple

# Import stage entrypoints
from stages.stage_01_clean_stations import run as run_stage_01
from stages.stage_02_generate_nodes import run as run_stage_02
from stages.stage_03_generate_station_layouts import run as run_stage_03

# If/when you implement Stage 03, uncomment and wire it here:
# from stages.stage_03_generate_station_layouts import run as run_stage_03


# Map stage number -> (human-readable name, callable)
STAGES: Dict[int, Tuple[str, Callable[..., None]]] = {
    1: ("Stage 01 - Clean Stations", run_stage_01),
    2: ("Stage 02 - Generate Nodes", run_stage_02),
    3: ("Stage 03 - Generate Station Layout", run_stage_03),
}


def run_selected_stages(start: int, end: int, debug_mode: bool = False) -> None:
    """Execute stages from `start` to `end` (both inclusive).

    Args:
        start: First stage number to run (must exist in STAGES to be executed).
        end: Last stage number to run (inclusive).
        debug_mode: When True, forwards a debug flag to each stage's `run()`.

    Behavior:
        - Iterates over the integer range [start, end].
        - For each stage number, looks up a `(name, func)` pair in STAGES.
        - If the stage is defined, prints a banner, calls `func(debug=debug_mode)`,
          and prints a completion message.
        - If the stage is NOT defined, prints a warning and continues.
    """
    for i in range(start, end + 1):
        name, func = STAGES.get(i, (None, None))
        if not func:
            print(f"⚠️  Stage {i} is not defined, skipping.")
            continue
        print(f"\n🚀 Running {name}")
        func(debug=debug_mode)
        print("✅ Done\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run one or more pipeline stages by index."
    )
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="First stage to run (default: 1).",
    )
    parser.add_argument(
        "--end",
        type=int,
        help="Last stage to run (inclusive). Defaults to --start if omitted.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose logging inside the stages.",
    )

    args = parser.parse_args()
    end_stage = args.end if args.end is not None else args.start
    debug_mode = args.debug

    run_selected_stages(args.start, end_stage, debug_mode)

    print("🏁 Pipeline finished.")
