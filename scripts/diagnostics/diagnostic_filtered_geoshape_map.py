import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pandas as pd
import folium
from folium import features
from pyproj import Transformer
from utils.constants import FILTERED_SUB_NETWORK_POLYGON_FILE

# 📍 EPSG:2056 → WGS84 dönüşüm
transformer = Transformer.from_crs("epsg:2056", "epsg:4326", always_xy=True)

# 📥 Veri yükle
df = pd.read_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, delimiter=';')

# 🌍 Harita nesnesi
m = folium.Map(location=[46.8, 8.3], zoom_start=8)

# 🎨 Her line_id için renk seçimi
color_list = [
    'red', 'blue', 'green', 'purple', 'orange', 'darkred',
    'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue',
    'darkpurple', 'white', 'pink', 'lightblue', 'lightgreen',
    'gray', 'black', 'lightgray'
]
line_ids = df['Linie'].unique()
color_map = {line_id: color_list[i % len(color_list)] for i, line_id in enumerate(line_ids)}

# 🛤️ Her segmenti çiz
for idx, row in df.iterrows():
    line_id = row['Linie']
    color = color_map.get(line_id, 'gray')
    start_op = row['START_OP']
    end_op = row['END_OP']

    # Geo shape parse
    geo_str = row['Geo shape'].replace("'", '"')
    try:
        coords = pd.json_normalize(eval(geo_str))['coordinates'][0]
    except Exception:
        continue

    if not coords or len(coords) < 2:
        continue

    # EPSG dönüşüm
    coords_wgs = [transformer.transform(x, y)[::-1] for x, y in coords]

    # Çiz
    folium.PolyLine(coords_wgs, color=color, weight=3, tooltip=f"{start_op} - {end_op} ({line_id})").add_to(m)

    # Start ve end noktalarına O işareti
    folium.Marker(
        coords_wgs[0],
        icon=features.DivIcon(icon_size=(150,36), icon_anchor=(7,20),
            html=f'<div style="font-size:10pt; color:yellow;">O {start_op}</div>')
    ).add_to(m)
    folium.Marker(
        coords_wgs[-1],
        icon=features.DivIcon(icon_size=(150,36), icon_anchor=(7,20),
            html=f'<div style="font-size:10pt; color:yellow;">O {end_op}</div>')
    ).add_to(m)

# 💾 Kaydet
output_path = r"D:\PhD\dec2025\filtered_line_geoshapes_map.html"
m.save(output_path)
print(f"✅ Map saved to: {output_path}")
