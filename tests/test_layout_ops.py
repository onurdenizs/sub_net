# tests/test_layout_ops.py
# -*- coding: utf-8 -*-
import pandas as pd

from utils.layout_ops import (
    build_throat_hubs_for_station,
    estimate_station_axis_from_hubs,
)


def test_build_throat_hubs_for_station_basic():
    row = pd.Series(
        {
            "station": "OL",
            "entry_nodes": str(
                [
                    {"Direction": "West", "Coordinates": [2600000.0, 1200000.0]},
                    {"Direction": "West", "Coordinates": [2600005.0, 1200000.0]},
                    {"Direction": "East", "Coordinates": [2600500.0, 1200000.0]},
                ]
            ),
        }
    )
    hubs = build_throat_hubs_for_station(row)
    assert "West" in hubs and "East" in hubs
    assert len(hubs["West"]) >= 1
    assert len(hubs["East"]) == 1

    axis = estimate_station_axis_from_hubs(hubs)
    assert axis is not None
    vx, vy = axis
    assert vx > 0  # east minus west should be positive X in this synthetic case
