import os

import pandas as pd

# ────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────
CSV_PATH = "D:\PhD\dec2025\data\raw\linie_mit_polygon.csv"


# ────────────────────────────────────────────────
# Diagnostics
# ────────────────────────────────────────────────
def diagnose_csv(path):
    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        return

    df = pd.read_csv(path, sep=";", low_memory=False)

    print("🧾 CSV Diagnostics Report")
    print("────────────────────────────")
    print(f"📂 File Path : {path}")
    print(f"📄 File Name : {os.path.basename(path)}")
    print(f"🔢 Number of Rows : {len(df)}")
    print("\n📌 Column Titles:")
    print(df.columns.tolist())

    print("\n🧬 Column Data Types:")
    print(df.dtypes)

    print("\n🔍 First 5 Rows:")
    print(df.head())


# ────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────
if __name__ == "__main__":
    diagnose_csv(CSV_PATH)
