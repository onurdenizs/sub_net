# diagnostic_multi_entry_point_approach_map.py
import pandas as pd
import folium
import json
import logging
import re
import ast
from pyproj import Transformer

# ────────────────────────────────
# ✅ Logger yapılandırması
# ────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# ────────────────────────────────
# ✅ Dosya yolları
# ────────────────────────────────
station_info_path = r"D:\PhD\dec2025\data\processed\station_info_master.csv"
segment_data_path = r"D:\PhD\dec2025\data\processed\filtered_sub_network_data.csv"
perronkante_path = r"D:\PhD\dec2025\data\raw\perronkante.csv"
output_map_path = r"D:\PhD\dec2025\multi_entry_node.html"

# ────────────────────────────────
# ✅ Koordinat dönüşüm sistemi
# ────────────────────────────────
# always_xy=True => transformer.transform(x, y) --> (lon, lat)
transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)

# İsviçre kaba sınırları (validasyon için)
CH_LAT_MIN, CH_LAT_MAX = 45.5, 47.9
CH_LON_MIN, CH_LON_MAX = 5.5, 10.8


# ────────────────────────────────
# ✅ Yardımcılar
# ────────────────────────────────
def safe_json_or_literal(s):
    """
    JSON string (tek/çift tırnaklı) ya da Python list/dict stringini güvenli biçimde liste/sözlüğe çevir.
    """
    if isinstance(s, (list, dict)):
        return s
    if pd.isna(s):
        return None
    txt = str(s).strip()
    # Önce JSON dene
    try:
        return json.loads(txt.replace("'", '"'))
    except Exception:
        pass
    # Sonra literal dene
    try:
        return ast.literal_eval(txt)
    except Exception:
        return None


def parse_pair(s):
    """
    '2683282.96,1248030.25' / '[2683282.96, 1248030.25]' / '8.54 47.37' gibi
    stringlerden iki sayıyı (x,y) olarak çek.
    """
    if pd.isna(s):
        raise ValueError("empty coord")
    nums = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', str(s))
    if len(nums) < 2:
        raise ValueError(f"could not parse two numbers from {s!r}")
    return float(nums[0]), float(nums[1])


def ensure_latlon(x, y):
    """
    (x,y) çifti WGS84 ölçeğinde gibi görünüyorsa (|x|≤180, |y|≤90) -> (lat,lon) = (y,x)
    değilse EPSG:2056->4326 dönüştürüp (lat,lon) döndür.
    """
    if abs(x) <= 180 and abs(y) <= 90:
        lat, lon = y, x
    else:
        lon, lat = transformer.transform(x, y)  # returns (lon, lat)
    return (lat, lon)


def in_switzerland(lat, lon):
    return (CH_LAT_MIN <= lat <= CH_LAT_MAX) and (CH_LON_MIN <= lon <= CH_LON_MAX)


# ────────────────────────────────
# ✅ CSV Dosyalarını oku
# ────────────────────────────────
station_df = pd.read_csv(station_info_path, delimiter=";")
segment_df = pd.read_csv(segment_data_path, delimiter=";")
try:
    perronkante_df = pd.read_csv(perronkante_path, delimiter=";", on_bad_lines='skip')
    logging.info("✅ perronkante.csv başarıyla okundu.")
except Exception as e:
    logging.error(f"❌ perronkante.csv okunamadı: {e}")
    perronkante_df = pd.DataFrame()

# ────────────────────────────────
# ✅ Harita başlat
# ────────────────────────────────
m = folium.Map(location=[46.8, 8.3], zoom_start=8, tiles='cartodbpositron')

# ────────────────────────────────
# ✅ Segmentleri çiz
# ────────────────────────────────
seg_ok, seg_fail = 0, 0
for _, row in segment_df.iterrows():
    try:
        coords_raw = safe_json_or_literal(row.get('_coordinates'))
        if not coords_raw:
            # Bazı dosyalarda _coordinates yoksa Geo shape'ten de deneyebiliriz
            coords_raw = safe_json_or_literal(row.get('Geo shape', ''))
            if isinstance(coords_raw, dict):
                coords_raw = coords_raw.get('coordinates', None)

        if not coords_raw or len(coords_raw) < 2:
            raise ValueError("no coordinates")

        points = []
        for x, y in coords_raw:
            lat, lon = ensure_latlon(x, y)
            points.append((lat, lon))

        folium.PolyLine(points, color='blue', weight=2, opacity=0.7).add_to(m)

        # Start & End noktaları (sariler)
        folium.CircleMarker(
            location=points[0], radius=4, color='yellow', fill=True, fill_color='yellow',
            tooltip=f"START: {row.get('START_OP', '')}"
        ).add_to(m)
        folium.CircleMarker(
            location=points[-1], radius=4, color='yellow', fill=True, fill_color='yellow',
            tooltip=f"END: {row.get('END_OP', '')}"
        ).add_to(m)
        seg_ok += 1
    except Exception as e:
        logging.warning(f"Segment plot error on row {row.name}: {e}")
        seg_fail += 1
logging.info(f"Segments drawn: ok={seg_ok}, failed={seg_fail}")

# ────────────────────────────────
# ✅ Entry node’ları çiz (siyah X)
# ────────────────────────────────
entry_ok, entry_fail = 0, 0
for _, row in station_df.iterrows():
    try:
        entry_nodes_raw = safe_json_or_literal(row.get('entry_nodes'))
        if not entry_nodes_raw:
            continue
        for node in entry_nodes_raw:
            coords = node.get('Coordinates')
            if not coords or len(coords) < 2:
                continue
            x, y = coords[0], coords[1]
            lat, lon = ensure_latlon(x, y)
            folium.Marker(
                location=(lat, lon),
                icon=folium.Icon(color='black', icon='remove', prefix='fa'),
                tooltip=f"ENTRY: {node.get('Connected Station','?')} ({node.get('Direction','?')})"
            ).add_to(m)
            entry_ok += 1
    except Exception as e:
        logging.warning(f"Entry node plot error on station {row.get('station', 'unknown')}: {e}")
        entry_fail += 1
logging.info(f"Entry nodes drawn: ok={entry_ok}, failed={entry_fail}")

# ────────────────────────────────
# ✅ Perronkante platform uçlarını çiz (kırmızı daire + kırmızı çizgi)
# ────────────────────────────────
pk_ok, pk_fail = 0, 0
if not perronkante_df.empty:
    for idx, row in perronkante_df.iterrows():
        try:
            x1, y1 = parse_pair(row['1_coord'])
            x2, y2 = parse_pair(row['2_coord'])

            latlon1 = ensure_latlon(x1, y1)
            latlon2 = ensure_latlon(x2, y2)

            # İsviçre sınırı dışında kaldıysa (y,x) swap denemesi
            if not in_switzerland(*latlon1) or not in_switzerland(*latlon2):
                latlon1_alt = ensure_latlon(y1, x1)
                latlon2_alt = ensure_latlon(y2, x2)
                if in_switzerland(*latlon1_alt) and in_switzerland(*latlon2_alt):
                    latlon1, latlon2 = latlon1_alt, latlon2_alt

            platform_label = str(row.get("Platform number", "")).strip()

            folium.CircleMarker(
                location=latlon1,
                radius=6,
                color='red',
                fill=True,
                fill_color='red',
                fill_opacity=1.0,
                tooltip=f"Platform: {platform_label}"
            ).add_to(m)

            folium.CircleMarker(
                location=latlon2,
                radius=6,
                color='red',
                fill=True,
                fill_color='red',
                fill_opacity=1.0
            ).add_to(m)

            folium.PolyLine(
                locations=[latlon1, latlon2],
                color='red',
                weight=2,
                opacity=0.8
            ).add_to(m)

            pk_ok += 1
        except Exception as e:
            logging.warning(f"Perronkante plot error on row {idx}: {e}")
            pk_fail += 1
    logging.info(f"perronkante drawn: ok={pk_ok}, failed={pk_fail}")
else:
    logging.info("perronkante.csv boş veya okunamadı; platform uçları çizilmedi.")

# ────────────────────────────────
# ✅ Haritayı kaydet
# ────────────────────────────────
m.save(output_map_path)
logging.info(f"✅ Map saved to {output_map_path}")
