import pandas as pd
import os

def run():
    print("🧼 Stage 01: Cleaning station data...")

    input_path = "data/raw/haltestellen_2025.csv"
    output_path = "data/interim/cleaned_stations.csv"

    # Dosya mevcut mu?
    if not os.path.exists(input_path):
        print(f"❌ Hata: Girdi dosyası bulunamadı: {input_path}")
        return

    # Veriyi oku
    df = pd.read_csv(input_path)

    # Örnek temizlik işlemi
    if "station_id" in df.columns:
        df_clean = df.dropna(subset=["station_id"])
    else:
        print("⚠️ Uyarı: 'station_id' kolonu bulunamadı, dosya olduğu gibi kopyalanacak.")
        df_clean = df

    # Sonuçları kaydet
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_clean.to_csv(output_path, index=False)

    print(f"✅ Cleaned data saved to {output_path}")
