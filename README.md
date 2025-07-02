# Swiss Railway Network Simulation with Virtual Coupling

This project aims to simulate the Swiss railway network in SUMO (Simulation of Urban MObility) with the ultimate goal of evaluating the impact of **Virtual Coupling (VC)** on operational KPIs such as **capacity**, **energy efficiency**, **emissions**, and **safety**.

The project is structured as a modular Python pipeline that processes raw Swiss railway data, builds simulation-ready networks, and integrates real-time VC logic using the **TraCI** interface.

---

## 🚀 Project Goals

- Parse and clean raw infrastructure datasets (stations, platform edges, tracks)
- Construct a realistic railway network compatible with SUMO
- Implement real-time decision-making modules for VC coupling/uncoupling
- Run comparative simulations of coupled vs. uncoupled train operations
- Analyze simulation outputs (delays, emissions, power consumption)

---

## 🧱 Project Structure


📁 .git
    📄 COMMIT_EDITMSG
    📄 FETCH_HEAD
    📄 HEAD
    📄 ORIG_HEAD
    📄 config
    📄 description
    📁 hooks
        📄 applypatch-msg.sample
        📄 commit-msg.sample
        📄 fsmonitor-watchman.sample
        📄 post-update.sample
        📄 pre-applypatch.sample
        📄 pre-commit.sample
        📄 pre-merge-commit.sample
        📄 pre-push.sample
        📄 pre-rebase.sample
        📄 pre-receive.sample
        📄 prepare-commit-msg.sample
        📄 push-to-checkout.sample
        📄 update.sample
    📄 index
    📁 info
        📄 exclude
    📁 logs
        📄 HEAD
        📁 refs
            📁 heads
                📄 main
            📁 remotes
                📁 origin
                    📄 main
    📁 objects
        📁 01
            📄 462ddeae86e481c4ad9e6307573e5dfe6b13f4
        📁 08
            📄 1fbe24f77e611e97dcf6b0199e3fb89f17c040
        📁 10
            📄 9aa2de82659a38dff0766fca9e94c85b4b31db
        📁 11
            📄 8db824db4269aa52833e22b3b3fc129c09afe5
        📁 16
            📄 b335257e9ea14cdf7b50f76981b1b755ea9dcc
        📁 25
            📄 e9b3ac4fba2ab8c916c259c085c4f88f76fa56
        📁 34
            📄 85bd4715073b4fe6a7af30cbaf5ef1be1ed51f
        📁 38
            📄 482cd0df1db93fa701ad49050bbd2bae107a7b
            📄 7d74fb7260dc6aee20508b627c564ab5c43164
        📁 46
            📄 3c5368ea3ffb2da996479f011cdf58712e0730
        📁 48
            📄 23f4a9df10abbe837777aa19f863f470cb6e15
        📁 4a
            📄 87824d84b4e5530d976a81f0163a1c75f23d6f
        📁 4b
            📄 7607b19d8621628bb845755d8fc4f50814bf5d
        📁 52
            📄 71be9cedd5dcb957964343e95fa2ca3e26f262
        📁 5c
            📄 51c92bd7b55ddd1f192aae2dce0e725d5da663
        📁 61
            📄 85d0c10639dd03acb2eb8b6ed359370b312934
            📄 f3bd7802b6126cc06672bc2b01a039d9db7b51
        📁 68
            📄 4b0401d05e15256793266a7e76122aca32aef9
        📁 6b
            📄 66cae997c36a1b3081d3c631672f5c15d0c10f
        📁 6e
            📄 24805e9134eeda46c0695cc8623bb41190d357
        📁 75
            📄 1cf4ada643c55887ade7ab41d14c4160b45afe
        📁 7a
            📄 1d9620b3baffe7a739a2badedda9080f61522f
        📁 85
            📄 d97b99994ac5c9fce5798d3fd3974e7062dca7
        📁 86
            📄 af832e55e348a684ef6706f22a3fa86ab9220a
        📁 8f
            📄 ad25c98547323457ec67b89988b7ef34e9b00b
        📁 94
            📄 592698cec9fa9d42633e252ad0abd418fa49b5
        📁 97
            📄 dabbbd897a3b5a2f38ed8d3b49d108505d161a
        📁 9b
            📄 d8e19d4dc72132e7f2d1daa3ac7297e26e016b
        📁 a0
            📄 eab1c65124c802985bbc98f8598c30588bd63e
        📁 a5
            📄 6d8309bd6fc6245399f52466b2cfd7f71b6a71
            📄 9f1dbc17b282dd26cacac69031ef1453bdb7fd
        📁 b2
            📄 4c1ad6b9ceb75edae81096cda51daf5d76a8d2
        📁 c8
            📄 97be9e81d4676747ee7f7dc5fd167352353e7f
        📁 d0
            📄 a08f4b86d39868d0a36c041a765d4307da7799
        📁 d5
            📄 a353c0d0091d6fdd640df78fe37f053b916283
        📁 da
            📄 7d9bb29a9e3e7e33611f0def7c249b05ab260c
        📁 dd
            📄 6fc0a88411f59dde1c517dcb9108ae1b508b0a
        📁 e2
            📄 43afead642271ccc4e604f29d9f129d3f456d1
        📁 e6
            📄 9de29bb2d1d6434b8b29ae775ad8c2e48c5391
        📁 e9
            📄 b12669aa16caefc99a49afab62f2f4cd30d74f
        📁 ea
            📄 577de57f201ee45fdce94aea8dbb0278415619
        📁 ec
            📄 bcb0cd8908055e6d2101e3664b706d8a6d90ea
        📁 ee
            📄 2a27469d5fe8fc7b88743588ffc862a2adc8db
        📁 info
        📁 pack
    📁 refs
        📁 heads
            📄 main
        📁 remotes
            📁 origin
                📄 main
        📁 tags
            📄 v0.2.0
📄 .gitignore
📄 README.md
📁 SUMO
    📁 inputs
        📁 sub_net
📁 archive
    📁 AI Prompts
        📄 Stage 1.txt
        📄 edges.txt
        📄 stage 0.txt
        📄 station_layout.txt
    📄 print_structure.py
📁 data
    📁 interim
    📁 processed
    📁 raw
        📄 2025-04-04_istdaten.csv
        📄 actual_date-world-traffic_point-2025-04-05.csv
        📄 actual_date_line_versions_2025-04-05.csv
        📄 dienststellen-gemass-opentransportdataswiss.csv
        📄 haltestelle-haltekante.csv
        📄 haltestellen_2025.csv
        📄 ist_daten_sbb.csv
        📄 jahresformation.csv
        📄 linie-mit-betriebspunkten.csv
        📄 linie.csv
        📄 linie_mit_polygon.csv
        📄 linienkilometrierung.csv
        📄 network_raw_data_info.txt
        📄 perron.csv
        📄 perronkante.csv
        📄 perronkante_epsg4326.csv
        📄 perronoberflache.csv
        📄 raw_dataset_info.txt
        📄 rollmaterial-matching.csv
        📄 rollmaterial.csv
        📄 sbbs_route_network.csv
        📄 zugzahlen.csv
📁 output
📁 reports
📄 requirements.txt
📄 run_pipeline.py
📁 scripts
    📁 dataset analysis
        📄 diagnose_csv_directory.py
        📄 diagnose_csv_structure.py
    📁 diagnostics
        📄 diagnostic_perronkante_data.py
        📄 diagnostic_polygon_data.py
    📁 network_scripts
    📁 postprocessing
    📁 preprocessing
    📁 simulation
    📁 tests
📁 stages
    📁 __pycache__
        📄 stage_01_clean_stations.cpython-311.pyc
    📄 stage_01_clean_stations.py
📁 tests


---

## 📂 Datasets Used

| File                      | Description                               |
|---------------------------|-------------------------------------------|
| `linie_mit_polygon.csv`   | Contains track segments and geometry info |
| `perronkante.csv`         | Contains platform edge and station info   |

These datasets are published by [opentransportdata.swiss](https://opentransportdata.swiss) and use **EPSG:2056** projection.

---

## 🔁 Running the Pipeline

You can run specific stages or the entire pipeline via CLI:

```bash
python run_pipeline.py --start 1 --end 3

For example, to run only stage 01:
python run_pipeline.py --start 1


🧪 Diagnostics

Diagnostic scripts can be found in the scripts/diagnostics/ folder:

    diagnostic_polygon_data.py: Analyze track segments and geometry distances

    diagnostic_perronkante_data.py: Analyze station platform data

Example usage:

python scripts/diagnostics/diagnostic_polygon_data.py
🛠️ Dependencies

    Python 3.10+

    pandas

    geopandas

    shapely

    pyproj

    matplotlib (optional for plots)

    SUMO (via TraCI)

Environment setup with Conda (recommended):

conda create -n progress_env python=3.10
conda activate progress_env
pip install -r requirements.txt


📈 Long-Term Vision

This simulation framework will serve as the backbone for multiple virtual coupling decision modules based on machine learning, rule-based logic, and hybrid strategies. Comparative scenarios will be evaluated for their impact on rail operations.
👤 Author

Onur Deniz
PhD Candidate in Railway Engineering
✈️ Commercial Airline Pilot turned Railway Researcher
📍 Istanbul
📃 License

MIT License. See LICENSE.md for details.


