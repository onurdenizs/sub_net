# -*- coding: utf-8 -*-
"""
Explode entry_nodes → one row per entry node.
Reads:  data/processed/station_info_master.csv  (semicolon ; delimited)
Writes: data/processed/entry_nodes_points.csv   (comma , delimited)
"""

import ast
import json
from pathlib import Path

import pandas as pd

IN_CSV = Path("data/processed/station_info_master.csv")
OUT_CSV = Path("data/processed/entry_nodes_points.csv")


def parse_nodes(raw):
    s = str(raw)
    try:
        return json.loads(s.replace("'", '"'))
    except Exception:
        try:
            return ast.literal_eval(s)
        except Exception:
            return []


def main():
    df = pd.read_csv(IN_CSV, delimiter=";")
    rows = []
    for _, r in df.iterrows():
        station = r.get("station", "")
        nodes = parse_nodes(r.get("entry_nodes", "[]"))
        for node in nodes:
            coords = node.get("Coordinates", [None, None])
            if not coords or coords[0] is None or coords[1] is None:
                continue
            x = float(coords[0])
            y = float(coords[1])
            side = node.get("Direction", "")
            connected = node.get("Connected Station", "")
            line = node.get("Line", "")
            rows.append(
                {
                    "station": station,
                    "side": side,
                    "connected": connected,
                    "line": line,
                    "x": x,
                    "y": y,
                    "wkt": f"POINT ({x} {y})",  # convenience WKT
                }
            )

    out = pd.DataFrame(
        rows, columns=["station", "side", "connected", "line", "x", "y", "wkt"]
    )
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"✅ Wrote {len(out)} entry nodes → {OUT_CSV.resolve()}")


if __name__ == "__main__":
    main()
