import pandas as pd
import json
import folium
from folium.plugins import MarkerCluster
import logging
from pyproj import Transformer

from utils.constants import (
    FILTERED_SUB_NETWORK_POLYGON_FILE,
    STATION_HELPER_FILE,
    STATION_ENTRY_NODE_FILE
)

def parse_geo_shape(geo_shape_str):
    try:
        geojson = json.loads(geo_shape_str.replace("'", '"'))
        return geojson['coordinates']
    except Exception as e:
        logging.warning(f"⚠️ Failed to parse geo shape: {e}")
        return []

def transform_coords(coord_list, transformer):
    """Transform list of [x, y] from EPSG:2056 to [lat, lon] EPSG:4326."""
    return [list(transformer.transform(x, y)[::-1]) for x, y in coord_list]

def plot_station_diagnostics():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logging.info("🚀 Loading data...")

    try:
        polygon_df = pd.read_csv(FILTERED_SUB_NETWORK_POLYGON_FILE, delimiter=';')
        station_df = pd.read_csv(STATION_HELPER_FILE)
        with open(STATION_ENTRY_NODE_FILE, 'r', encoding='utf-8') as f:
            entry_nodes = json.load(f)
    except Exception as e:
        logging.error(f"❌ Failed to load input files: {e}")
        return

    # EPSG:2056 → EPSG:4326 transformer
    transformer = Transformer.from_crs(2056, 4326, always_xy=True)

    m = folium.Map(location=[46.8182, 8.2275], zoom_start=8)
    marker_cluster = MarkerCluster().add_to(m)

    # Plot GeoShapes (red polylines)
    logging.info("🔴 Plotting segment lines...")
    for idx, row in polygon_df.iterrows():
        coords = parse_geo_shape(row.get('Geo shape', ''))
        if coords:
            transformed_coords = transform_coords(coords, transformer)
            folium.PolyLine(
                locations=transformed_coords,
                color='red',
                weight=2,
                opacity=0.7
            ).add_to(m)

    # Plot center coordinates (blue X + station code)
    logging.info("🔵 Plotting station centers...")
    for idx, row in station_df.iterrows():
        center = row.get('center_coordinates')
        station = row.get('station')
        if isinstance(center, str):
            try:
                center = json.loads(center.replace("'", '"'))
            except Exception as e:
                logging.warning(f"⚠️ Failed to parse center_coordinates for {station}: {e}")
                continue
        if center:
            latlon = transformer.transform(center[0], center[1])[::-1]
            folium.Marker(
                location=latlon,
                icon=folium.DivIcon(
                    html=f'<div style="color:blue;font-size:12px;">✕ {station}</div>'
                )
            ).add_to(marker_cluster)

    # Plot entry nodes (yellow circles)
    logging.info("🟡 Plotting entry nodes...")
    for station, directions in entry_nodes.items():
        for direction, coord in directions.items():
            if coord:
                latlon = transformer.transform(coord[0], coord[1])[::-1]
                folium.CircleMarker(
                    location=latlon,
                    radius=4,
                    color='yellow',
                    fill=True,
                    fill_opacity=0.9
                ).add_to(m)

    output_file = 'station_diagnostics_map.html'
    m.save(output_file)
    logging.info(f"✅ Interactive map saved as {output_file}")

if __name__ == '__main__':
    plot_station_diagnostics()
