import argparse

# Aşamaları import et
from stages.stage_01_clean_stations import run as run_stage_01
from stages.stage_02_generate_nodes import run as run_stage_02
from stages.stage_03_generate_hubs import run as run_stage_03  # <-- NEW

# from stages.stage_03_generate_edges import run as run_stage_03

# Stage numarası: (isim, fonksiyon)
STAGES = {
    1: ("Stage 01 - Clean Stations", run_stage_01),
    2: ("Stage 02 - Generate Nodes", run_stage_02),
    3: ("Stage 03 - Generate Hubs & Axis", run_stage_03),  # <-- NEW
}


def run_selected_stages(start: int, end: int, debug_mode=False):
    for i in range(start, end + 1):
        name, func = STAGES.get(i, (None, None))
        if not func:
            print(f"⚠️ Stage {i} tanımlı değil, atlanıyor.")
            continue
        print(f"\n🚀 Running {name}")
        func(debug=debug_mode)
        print("✅ Done\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run selected pipeline stages.")
    parser.add_argument(
        "--start", type=int, default=1, help="Başlangıç aşaması (varsayılan: 1)"
    )
    parser.add_argument(
        "--end", type=int, help="Bitiş aşaması (varsayılan: start ile aynı)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()
    end_stage = args.end if args.end is not None else args.start
    debug_mode = args.debug

    run_selected_stages(args.start, end_stage, debug_mode)

    print("🏁 Pipeline tamamlandı.")
