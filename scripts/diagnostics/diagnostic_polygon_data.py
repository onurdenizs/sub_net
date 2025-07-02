import csv
import sys
import pandas as pd
import logging
import json
from collections import defaultdict
import math

# Alan sınırını yükselt (100 MB)
csv.field_size_limit(100 * 1024 * 1024)

# Logging ayarları
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger()

# GeoJSON biçimli Geo shape string'inden koordinatları çıkar
def parse_coords(geo_shape_str):
    try:
        geojson = json.loads(geo_shape_str.replace('""', '"'))
        if geojson.get("type") == "LineString":
            return geojson["coordinates"]
    except Exception:
        return []
    return []

# EPSG:2056 koordinatlarında uzunluk (metre) hesapla
def calculate_linestring_length(coords):
    def euclidean(p1, p2):
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])
    return sum(euclidean(coords[i], coords[i + 1]) for i in range(len(coords) - 1))

def main():
    file_path = "D:/PhD/dec2025/data/raw/linie_mit_polygon.csv"

    try:
        df = pd.read_csv(file_path, sep=";", encoding="utf-8", engine="python")
    except Exception as e:
        logger.error(f"CSV okunamadı: {e}")
        return

    # Benzersiz istasyon kısaltmalarını al
    start_ops = df["START_OP"].dropna().unique()
    end_ops = df["END_OP"].dropna().unique()
    all_stations = set(start_ops).union(set(end_ops))
    logger.info(f"\n📌 Toplam benzersiz istasyon sayısı: {len(all_stations)}\n")

    # Her istasyonun kaç farklı koordinatla temsil edildiğini analiz et
    station_coords = defaultdict(set)
    for _, row in df.iterrows():
        coords = parse_coords(row["Geo shape"])
        if not coords:
            continue
        if pd.notna(row["START_OP"]):
            station_coords[row["START_OP"]].add(tuple(coords[0]))
        if pd.notna(row["END_OP"]):
            station_coords[row["END_OP"]].add(tuple(coords[-1]))

    logger.info("🔍 Her bir istasyonun temsil edildiği farklı koordinat sayısı:")
    for station, coord_set in sorted(station_coords.items()):
        logger.info(f"  {station}: {len(coord_set)}")

    # Her satır için mesafe hesapla
    distances = []
    for _, row in df.iterrows():
        coords = parse_coords(row["Geo shape"])
        if coords and len(coords) >= 2:
            distances.append({
                "START_OP": row["START_OP"],
                "END_OP": row["END_OP"],
                "Distance_m": round(calculate_linestring_length(coords), 2)
            })

    dist_df = pd.DataFrame(distances)

    if dist_df.empty:
        logger.warning("\n⚠️ Poligon verisi boş, mesafe hesaplanamadı.")
        return

    logger.info("\n📏 En uzun 10 poligon:")
    logger.info(dist_df.sort_values(by="Distance_m", ascending=False)
                .head(10)[["START_OP", "END_OP", "Distance_m"]])

    logger.info("\n📏 En kısa 10 poligon:")
    logger.info(dist_df.sort_values(by="Distance_m", ascending=True)
                .head(10)[["START_OP", "END_OP", "Distance_m"]])

if __name__ == "__main__":
    main()
