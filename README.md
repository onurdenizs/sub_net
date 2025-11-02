# 🚄 Swiss Railway Network Simulation with Virtual Coupling

This project simulates the **Swiss railway network** using [**SUMO** (Simulation of Urban MObility)](https://www.eclipse.org/sumo/).  
It serves as part of an academic research effort to evaluate the impact of **Virtual Coupling (VC)** on railway operations, focusing on **capacity**, **energy efficiency**, **emissions**, and **safety**.

The system is implemented as a **modular, multi-stage Python pipeline** that:
1. Parses and cleans raw infrastructure data,
2. Builds a realistic simulation-ready railway network,
3. Generates geometry layouts, nodes, and edges,
4. Integrates real-time Virtual Coupling logic through the **TraCI API**.

---

## 🎯 Research & Engineering Goals

- ✅ Clean and standardize Swiss railway datasets (stations, platforms, segments)  
- ✅ Build a SUMO-compatible rail network reflecting real geometry and topology  
- ✅ Implement real-time VC logic for coupling / decoupling / safety control  
- ✅ Run comparative simulations between VC and conventional operations  
- ✅ Analyze key performance indicators (delay, headway, emissions, energy)

---

## 🧠 Project Overview

| Stage | Script | Description |
|-------|---------|-------------|
| **Stage 00** | `stage_00_prepare_master.py` | Prepare master datasets, harmonize column names, define constants |
| **Stage 01** | `stage_01_clean_stations.py` | Filter, merge, and clean raw station and segment data |
| **Stage 02** | `stage_02_generate_nodes.py` | Generate nodes and entry points for all stations |
| **Stage 03** | `stage_03_generate_station_layouts.py` | Build station-specific layout definitions |
| **Stage 04** | `stage_04_generate_station_layout_geometry.py` | Compute geometry and SUMO-ready layouts (edges, nodes, coordinates) |

All stages are orchestrated via the **`run_pipeline.py`** controller, which allows partial or full pipeline execution.

---

## 🧱 Repository Structure

```bash
📦 sub_net/
│
├─ stages/                    # All pipeline stages (00–04)
├─ utils/                     # Core geometry, layout, and GIS utilities
│   ├─ geo_ops.py
│   ├─ layout_builders.py
│   ├─ layout_primitives.py
│   ├─ polyline_ops.py
│   └─ constants.py
│
├─ tools/                     # Diagnostic / helper scripts
├─ data/
│   ├─ raw/                   # Raw opentransportdata.swiss datasets
│   ├─ processed/             # Cleaned intermediate data
│   └─ diagnostics/           # Debug or validation outputs
│
├─ logs/                      # Runtime logs
├─ reports/                   # Analytical reports / maps (ignored by Git)
├─ run_pipeline.py             # Main execution controller
├─ requirements.txt / environment.yml
└─ README.md

---

## 🧭 Datasets

All input data are sourced from **[opentransportdata.swiss](https://opentransportdata.swiss)** and projected in **EPSG:2056 (CH1903+)**.

| File | Description |
|------|-------------|
| `linie_mit_polygon.csv` | Line segments with geometric polylines |
| `perronkante.csv` | Platform edges and station details |
| `dienststellen-gemass-opentransportdataswiss.csv` | Station metadata and coordinates |
| `zugzahlen.csv` | Train frequency / line identifiers (for VC scenarios) |

> ⚠️ These datasets are publicly available but may require preprocessing before use in SUMO simulations.

---

## ⚙️ Environment Setup

### 🧩 Conda (recommended)
```bash
conda create -n progress_env python=3.10
conda activate progress_env
pip install -r requirements.txt


## 🧭 Datasets

All input data are sourced from https://opentransportdata.swiss and projected in **EPSG:2056 (CH1903+).**

| File                                                 | Description                                   |
|------------------------------------------------------|-----------------------------------------------|
| `linie_mit_polygon.csv`                              | Line segments with geometric polylines        |
| `perronkante.csv`                                    | Platform edges and station details            |
| `dienststellen-gemass-opentransportdataswiss.csv`    | Station metadata and coordinates               |
| `zugzahlen.csv`                                      | Train frequency / line identifiers (VC input) |

⚠️ These datasets are publicly available but often need column harmonization, CRS checks (→ 2056), and filtering before being used inside the SUMO pipeline.

---

## ⚙️ Environment Setup

### 1) Conda (recommended)

Create and activate the environment:

    conda create -n progress_env python=3.10
    conda activate progress_env
    pip install -r requirements.txt

(If you use `environment.yml` instead of `requirements.txt`, just run:  
`conda env create -f environment.yml` and then `conda activate progress_env`.)

### 2) Python version

- Target: **Python 3.10+** (your system currently uses 3.12 on QGIS but the repo is aimed at 3.10–3.11 for maximum library compatibility).
- SUMO / TraCI parts may require matching SUMO install on the machine.

---

## 📦 Key Dependencies

| Package / Tool               | Purpose                                 |
|------------------------------|-----------------------------------------|
| `pandas`, `geopandas`        | Tabular and geospatial data handling    |
| `shapely`, `pyproj`          | Geometry operations, CRS transforms     |
| `matplotlib`, `folium`       | Diagnostics, HTML map previews          |
| `sumolib`, `traci`           | SUMO API integration                    |
| `logging`, `argparse`        | Pipeline orchestration, CLI arguments   |
| `ruff`, `black`, `isort`     | Code quality, formatting, imports       |

Notes:
- `geopandas` + `shapely` + `pyproj` are essential for working with Swiss CH1903+ coordinates.
- `folium` is used to generate the HTML diagnostics you have in `reports/`.
- `ruff` / `black` / `isort` are optional but already configured in the repo to keep the codebase tidy.

---
## 🚀 Running the Pipeline

You can run the entire processing pipeline or specific stages directly from the command line.

### Run all stages (01–04)
    python run_pipeline.py --start 1 --end 4

### Run a single stage
    python run_pipeline.py --start 1

Each stage logs its progress, warnings, and output summary to `/logs/` and produces intermediate CSV files under `/data/processed/`.

### Example log excerpt
    🚀 Running Stage 03 - Generate Station Layouts
    2025-10-20 20:50:40,823 - INFO - Segments: 265 | Stations: 272
    2025-10-20 20:50:41,316 - INFO - ✅ Saved output: data/processed/station_design_master.csv

---

## 🧪 Diagnostics & Validation

All diagnostic and geometry-check tools are in:
- `tools/`
- `scripts/diagnostics/`

| Script | Function |
|---------|-----------|
| `diagnostic_polygon_data.py` | Validates continuity and topology of line geometries |
| `diagnostic_perronkante_data.py` | Checks consistency of platform and station data |
| `entry_node_diagnostics.py` | Visualizes station entry nodes and mainline alignment |

Each tool can be run independently:
    python scripts/diagnostics/diagnostic_polygon_data.py

They generate:
- Interactive HTML maps in `/reports/`
- Validation logs in `/data/diagnostics/`

---

## 🧩 Output Structure

| Folder | Description |
|---------|-------------|
| `data/processed/` | Clean intermediate datasets (per stage) |
| `data/diagnostics/` | Logs and validation summaries |
| `reports/` | Generated Folium maps and visual outputs |
| `SUMO/inputs/` | Final geometry and node files for simulation |
| `output/` | Scenario-based SUMO results (emissions, energy, delay) |

---

## 🧠 Recommended Workflow

1. Verify datasets under `data/raw/`
2. Run pipeline from Stage 00 → Stage 04
3. Open generated maps in `reports/` to visually confirm geometry
4. Export SUMO network files from `/SUMO/inputs/`
5. Run simulation and collect KPIs

---

Next step → **Part 3 (Git branching, code quality, research vision, author/license)**.
---

## 🌿 Git Branching & Development Workflow

This repository follows a **feature → integrate → stabilize** model that fits a staged Python/SUMO pipeline.

| Branch | Purpose |
|--------|---------|
| `main` | Stable, demoable, runs end-to-end |
| `dev`  | Integration branch (multiple stages touched) |
| `feat/...` | New functionality (e.g. `feat/station-orientation`) |
| `fix/...`  | Bug / regression fixes (e.g. `fix/issue-01-entry-on-mainline`) |
| `chore/...`| Repo cleanup, .gitignore, tooling, CI, formatting |
| `docs/...` | README, design notes, academic writeups |

Typical flow:

    git switch -c fix/issue-01-entry-on-mainline
    # …do the work…
    git commit -m "fix: corrected entry node snapping to mainline"
    git push origin fix/issue-01-entry-on-mainline
    # → open PR to dev → later squash/merge to main

Notes:

- Every stage change should mention which stage it touches: `stages:01`, `stages:03+utils`, etc.
- Data files under `data/processed/` must NOT be committed (already handled in .gitignore).
- SUMO input folders must be generated, not stored.

---

## 🧹 Code Quality & Conventions

This project tries to stay **boringly consistent** so that future you (and reviewers) can follow the logic across stages.

**Tools**

- `black` → formatting
- `isort` → imports
- `ruff` → fast linting
- `pytest` → unit / regression tests for geometry helpers
- `logging` → instead of `print()`
- `argparse` → CLI control for `run_pipeline.py`

**Style**

- Python ≥ 3.10
- Type hints everywhere (`list[tuple[float, float]]`, `dict[str, Any]`, etc.)
- Google-style docstrings

Example docstring (note: no extra code fences inside README so it can be copy–pasted):

    def compute_polygon_length(coords: list[tuple[float, float]]) -> float:
        """Compute the total length of a polyline in meters.

        Args:
            coords: List of (x, y) coordinates in EPSG:2056.

        Returns:
            Total length in meters.
        """
        ...

**Logging pattern**

- Each stage logs:
  - input rows
  - output rows
  - skipped / merged segments
  - file written with path
- Log levels: `INFO` for progress, `WARNING` for suspicious geometry, `ERROR` for missing files.

---

## 🔬 Research Vision

This repo is the **engineering backbone** of the PhD work on **Virtual Coupling (VC)** for Swiss (later DACH) railway networks.

**Research questions supported by this repo:**

1. What is the *realistic* headway reduction we get from VC if we respect Swiss infrastructure constraints?
2. How does mixed traffic (VC-capable + conventional) affect capacity and delay propagation?
3. Can we express coupling / decoupling as a real-time decision problem (TraCI) and test it in SUMO?
4. How big is the energy/emissions gain in dense corridors when we VC multiple trains?
5. Which station / junction geometries become bottlenecks when VC is enabled?

**Planned extensions**

- GTFS and DB/OpenData ingestion to extend Swiss network with German corridors
- ML-based VC selector (which trains to couple, when, based on KPIs)
- Safety layer: automatic uncoupling when geometry / schedule / braking distance becomes unsafe
- Visualization / dashboards for experiments

---

## 👤 Author

**Onur Deniz**  
PhD Candidate in Railway Engineering  
Commercial Airline Pilot → Railway / Transport Systems  
Istanbul Technical University (ITU)

GitHub: https://github.com/onurdenizs

---

## 📜 License

This project is released under the **MIT License**.  
You may use, modify, and redistribute with proper attribution.

---

## 📚 Citation

If you use this codebase or its generated datasets in academic work, please cite:

    Deniz, O. (2025). "Swiss Railway Network Simulation with Virtual Coupling."
    PhD Research Project, Istanbul Technical University.

---

✅ End of README
