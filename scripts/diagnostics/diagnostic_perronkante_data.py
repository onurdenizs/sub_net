import csv
import sys
import pandas as pd
import logging

# Alan sınırını artır (100 MB)
csv.field_size_limit(100 * 1024 * 1024)

# Logging ayarları
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger()

def main():
    file_path = "D:/PhD/dec2025/data/raw/perronkante.csv"

    try:
        df = pd.read_csv(file_path, sep=";", encoding="utf-8", engine="python")
    except Exception as e:
        logger.error(f"CSV okunamadı: {e}")
        return

    logger.info(f"\n📌 Toplam satır sayısı: {len(df)}")

    # Benzersiz istasyon sayısı
    unique_stations = df["Station abbreviation"].nunique()
    logger.info(f"🏷️ Benzersiz istasyon sayısı: {unique_stations}")

    # Platform uzunluğu istatistikleri
    platform_lengths = df["Length of platform edge"].dropna()
    logger.info(f"\n📏 Platform uzunluğu istatistikleri:")
    logger.info(f" - Ortalama: {platform_lengths.mean():.2f} m")
    logger.info(f" - Medyan: {platform_lengths.median():.2f} m")
    logger.info(f" - Min    : {platform_lengths.min():.2f} m")
    logger.info(f" - Max    : {platform_lengths.max():.2f} m")
    logger.info(f" - StdSap : {platform_lengths.std():.2f} m")

    # En kısa ve en uzun 10 platform
    sorted_lengths = df[["Station abbreviation", "Stop name", "Length of platform edge"]].dropna()
    sorted_lengths = sorted_lengths.sort_values(by="Length of platform edge")

    logger.info(f"\n📏 En kısa 10 platform:")
    logger.info(sorted_lengths.head(10).to_string(index=False))

    logger.info(f"\n📏 En uzun 10 platform:")
    logger.info(sorted_lengths.tail(10).to_string(index=False))

    # Daha doğru platform sayısı: istasyondaki benzersiz platform numaraları
    platform_counts = (
        df.groupby("Station abbreviation")["Platform number"]
        .nunique()
        .sort_values(ascending=False)
    )

    logger.info(f"\n🏗️ En fazla benzersiz platform numarasına sahip 10 istasyon:")
    logger.info(platform_counts.head(10).to_string())

if __name__ == "__main__":
    main()
