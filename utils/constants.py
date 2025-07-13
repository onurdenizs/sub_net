from pathlib import Path
LINE_ID_LIST = [850, 751, 710, 650, 540, 450, 250, 100, 501, 500,
                722, 723, 720, 890, 900, 150, 200, 210, 410, 250, 400, 452]
NEVER_SKIP_LIST = ['LZ', 'BS', 'BN', 'ZUE', 'LS', 'GE']
MIN_PLATFORM_LENGTH = 200         # meters
MAX_PLATFORM_LENGTH = 500         # meters
DEFAULT_PLATFORM_LENGTH = 350     # meters
ENTRY_OFFSET_BUFFER = 200         # meters
MIN_MAIN_LINE_LENGTH = 200        # meters
MAX_PLATFORM_COUNT = 20           # meters
MIN_PLATFORM_COUNT = 2            # meters
DEFAULT_PLATFORM_COUNT = 5        # meters
CLOSENESS_THRESHOLD = (
    MAX_PLATFORM_LENGTH + ENTRY_OFFSET_BUFFER * 2 + MIN_MAIN_LINE_LENGTH
)


PLATFORM_LENGTH_DECISION_METHOD = "X" #X: maximum platform length, N: for minimum platform length, A: Average platform length D: Default platform length
FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH = "N" #D:default platform length, N: Minimum platform length, X: Maximum platform length 
FILL_EMPTY_PLATFORM_NO_DATA_WITH = "N" #D:default platform count, N: Minimum platform count, X: Maximum platform count


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
POLYGON_FILE = RAW_DIR / "linie_mit_polygon.csv"
FILTERED_SUB_NETWORK_POLYGON_FILE = PROCESSED_DIR / "filtered_sub_network_data.csv"
OUTPUT_PLATFORM_FILE = PROCESSED_DIR / "station_platform_info.csv"
PLATFORM_FILE = RAW_DIR / "perronkante.csv"
STATION_HELPER_FILE = PROCESSED_DIR / "station_info.csv"
STATION_ENTRY_NODE_FILE = PROCESSED_DIR / "station_entry_nodes.json"

