from pathlib import Path

LINE_ID_LIST = [
    850,
    751,
    710,
    650,
    540,
    450,
    250,
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
MAX_PLATFORM_COUNT = 20  # meters
MIN_PLATFORM_COUNT = 2  # meters
DEFAULT_PLATFORM_COUNT = 5  # meters
DEFAULT_PLATFORM_OFFSET = 2  # meters
CLOSENESS_THRESHOLD = (
    MAX_PLATFORM_LENGTH + ENTRY_OFFSET_BUFFER * 2 + MIN_MAIN_LINE_LENGTH
)

# --- Station layout parameters -------------------------------------------------
TRACK_SPACING: float = 4.5  # meters between parallel tracks (center-to-center)
THROAT_MIN: float = 80.0  # minimum throat length per side (m)
THROAT_ALPHA: float = 0.28  # throat length ratio w.r.t platform length L (0.25–0.30)
SMOOTH_LEN: float = 25.0  # single shape-point smoothing length for sharp angles (m)
TURNBACK_LEN: float = 20.0  # short connector length for turnback edges (m)
BYPASS_ENABLED: bool = True  # create hub-to-hub bypass edge per station
LAYOUT_STRATEGY: str = "hybrid"  # 'hybrid': single-entry side uses entry==hub

# NOTE:
# ENTRY_OFFSET_BUFFER and MIN_MAIN_LINE_LENGTH remain as-is. ENTRY_OFFSET_BUFFER=500 m
# is typically sufficient to leave room for throats and smoothing.
PLATFORM_LENGTH_DECISION_METHOD = "X"  # X: maximum platform length, N: for minimum platform length, A: Average platform length D: Default platform length
FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH = "N"  # D:default platform length, N: Minimum platform length, X: Maximum platform length
FILL_EMPTY_PLATFORM_NO_DATA_WITH = "N"  # D:default platform count, N: Minimum platform count, X: Maximum platform count


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
POLYGON_FILE = RAW_DIR / "linie_mit_polygon.csv"
FILTERED_SUB_NETWORK_POLYGON_FILE = PROCESSED_DIR / "filtered_sub_network_data.csv"
STATION_INFO_FILE = PROCESSED_DIR / "station_platform_info.csv"
PLATFORM_FILE = RAW_DIR / "perronkante.csv"
STATION_HELPER_FILE = PROCESSED_DIR / "station_info_master.csv"
STATION_ENTRY_NODE_FILE = PROCESSED_DIR / "station_entry_nodes.json"
