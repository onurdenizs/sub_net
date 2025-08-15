import os

import pandas as pd

# ─────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────
CSV_DIRECTORY = "D:/PhD/dec2025/data/raw"  # 🔧 Change this as needed
OUTPUT_FILENAME = "raw_dataset_info.txt"


# ─────────────────────────────────────────────────────
# Diagnostics
# ─────────────────────────────────────────────────────
def diagnose_csv(path):
    try:
        df = pd.read_csv(path, sep=";", low_memory=False)
    except Exception as e:
        return f"❌ Error reading file: {path}\nReason: {e}\n{'─'*60}\n"

    report = []
    report.append("🧾 CSV Diagnostics Report")
    report.append("─" * 60)
    report.append(f"📂 File Path : {path}")
    report.append(f"📄 File Name : {os.path.basename(path)}")
    report.append(f"🔢 Number of Rows : {len(df)}")

    report.append("\n📌 Column Titles:")
    report.append(str(df.columns.tolist()))

    report.append("\n🧬 Column Data Types:")
    report.append(str(df.dtypes))

    report.append("\n🔍 First 5 Rows:")
    report.append(str(df.head()))

    report.append("─" * 60 + "\n")
    return "\n".join(report)


# ─────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────
def main():
    if not os.path.exists(CSV_DIRECTORY):
        print(f"❌ Directory does not exist: {CSV_DIRECTORY}")
        return

    output_path = os.path.join(CSV_DIRECTORY, OUTPUT_FILENAME)
    all_reports = []

    for file in os.listdir(CSV_DIRECTORY):
        if file.endswith(".csv"):
            full_path = os.path.join(CSV_DIRECTORY, file)
            print(f"📊 Diagnosing: {file}")
            report = diagnose_csv(full_path)
            print(report)
            all_reports.append(report)

    # Write all results into one txt file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(all_reports))

    print(f"✅ All diagnostics saved to: {output_path}")


if __name__ == "__main__":
    main()
