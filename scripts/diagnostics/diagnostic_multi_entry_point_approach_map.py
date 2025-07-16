import pandas as pd
import folium
import json
from pyproj import Transformer

# Dosya yolları
station_info_path = r"D:\PhD\dec2025\data\processed\station_info_master.csv"
segment_data_path = r"D:\PhD\dec2025\data\processed\filtered_sub_network_data.csv"
output_map_path = r"D:\PhD\dec2025\multi_entry_node.html"

# EPSG:2056 → WGS84 transformer
transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)

# Veri oku
station_df = pd.read_csv(station_info_path, delimiter=';')
segment_df = pd.read_csv(segment_data_path, delimiter=';')

# Haritayı başlat (İsviçre ortalamasına yakın bir merkez)
m = folium.Map(location=[46.8, 8.3], zoom_start=8, tiles='cartodbpositron')

# Segmentleri çiz
for _, row in segment_df.iterrows():
    try:
        coords_raw = json.loads(row['_coordinates'].replace("'", '"'))
        points = [transformer.transform(x, y)[::-1] for x, y in coords_raw]  # (lon, lat) → (lat, lon)
        folium.PolyLine(points, color='blue', weight=2, opacity=0.7).add_to(m)

        # Start_OP
        folium.CircleMarker(location=points[0],
                            radius=4,
                            color='yellow',
                            fill=True,
                            fill_color='yellow',
                            tooltip=f"START: {row['START_OP']}").add_to(m)
        # End_OP
        folium.CircleMarker(location=points[-1],
                            radius=4,
                            color='yellow',
                            fill=True,
                            fill_color='yellow',
                            tooltip=f"END: {row['END_OP']}").add_to(m)
    except Exception as e:
        print(f"Segment plot error on row {row.name}: {e}")

# Entry node'ları çiz
for _, row in station_df.iterrows():
    try:
        entry_nodes_raw = json.loads(row['entry_nodes'].replace("'", '"'))
        for node in entry_nodes_raw:
            x, y = node['Coordinates']
            latlon = transformer.transform(x, y)[::-1]
            folium.Marker(location=latlon,
                          icon=folium.Icon(color='black', icon='remove', prefix='fa'),
                          tooltip=f"ENTRY: {node['Connected Station']} ({node['Direction']})").add_to(m)
    except Exception as e:
        print(f"Entry node plot error on station {row.get('station', 'unknown')}: {e}")

# Haritayı kaydet
m.save(output_map_path)
print(f"✅ Map saved to {output_map_path}")
