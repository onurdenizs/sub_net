from pathlib import Path

LINE_ID_LIST = [
    850,
    751,
    710,
    650,
    540,
    450,
    100,
    501,
    500,
    722,
    723,
    720,
    890,
    900,
    150,
    200,
    210,
    410,
    250,
    400,
    452,
    451,
]
NEVER_SKIP_LIST = ["LZ", "BS", "BN", "ZUE", "LS", "GE"]  # , 'ABOW', 'ABO', 'RTR'
MIN_PLATFORM_LENGTH = 300  # meters
MAX_PLATFORM_LENGTH = 700  # meters
DEFAULT_PLATFORM_LENGTH = 400  # meters
ENTRY_OFFSET_BUFFER = 500  # meters
MIN_MAIN_LINE_LENGTH = 400  # meters
MAX_PLATFORM_COUNT = 20
MIN_PLATFORM_COUNT = 2
DEFAULT_PLATFORM_COUNT = 5
TRACK_SPACING_M = 4  # meters
PLATFORM_END_OFFSET_M = 0.0
TERMINUS_ONE_SIDED = False

AXIS_MIN_VECTORS = 2

AXIS_SPREAD_WARN_DEG = 25

THROAT_MAX_SKEW_DEG = 35
CLOSENESS_THRESHOLD = (
    MAX_PLATFORM_LENGTH + ENTRY_OFFSET_BUFFER * 2 + MIN_MAIN_LINE_LENGTH
)


PLATFORM_LENGTH_DECISION_METHOD = "X"  # X: maximum platform length, N: for minimum platform length, A: Average platform length D: Default platform length
FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH = "N"  # D:default platform length, N: Minimum platform length, X: Maximum platform length
FILL_EMPTY_PLATFORM_NO_DATA_WITH = "N"  # D:default platform count, N: Minimum platform count, X: Maximum platform count

NODE_ID_TEMPLATE = "STN_{station}_{role}_{side}_{trackIndex}_{seq}"
EDGE_ID_TEMPLATE = "STN_{station}_{role}_{trackIndex}_{seq}"

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
POLYGON_FILE = RAW_DIR / "linie_mit_polygon.csv"
FILTERED_SUB_NETWORK_POLYGON_FILE = PROCESSED_DIR / "filtered_sub_network_data.csv"
STATION_INFO_FILE = PROCESSED_DIR / "station_platform_info.csv"
PLATFORM_FILE = RAW_DIR / "perronkante.csv"
STATION_HELPER_FILE = PROCESSED_DIR / "station_info_master.csv"
STATION_ENTRY_NODE_FILE = PROCESSED_DIR / "station_entry_nodes.json"
# Stage 00 reference/master output:
STATION_MASTER_FILE = PROCESSED_DIR / "station_master.csv"
STATION_DESIGN_FILE = PROCESSED_DIR / "station_design_master.csv"
STATION_LAYOUT_NODES_FILE = PROCESSED_DIR / "station_layout_nodes.csv"
STATION_LAYOUT_EDGES_FILE = PROCESSED_DIR / "station_layout_edges.csv"
STATION_LAYOUT_REPORT_FILE = PROCESSED_DIR / "station_layout_geometry_report.txt"
