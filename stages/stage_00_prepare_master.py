import pandas as pd
import json
import logging
from utils.constants import (
    POLYGON_FILE, PLATFORM_FILE, PROCESSED_DIR, LINE_ID_LIST,
    MAX_PLATFORM_COUNT, MIN_PLATFORM_COUNT, DEFAULT_PLATFORM_COUNT,
    MAX_PLATFORM_LENGTH, MIN_PLATFORM_LENGTH, DEFAULT_PLATFORM_LENGTH,
    PLATFORM_LENGTH_DECISION_METHOD, FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH,
    FILL_EMPTY_PLATFORM_NO_DATA_WITH, STATION_MASTER_FILE, NEVER_SKIP_LIST
)
from utils.segment_ops import parse_geo_shape

def setup_logger(debug_mode=False):
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    return logger

def get_fallback_values():
    if FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH == "X":
        platform_length = MAX_PLATFORM_LENGTH
    elif FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH == "N":
        platform_length = MIN_PLATFORM_LENGTH
    else:
        platform_length = DEFAULT_PLATFORM_LENGTH

    if FILL_EMPTY_PLATFORM_NO_DATA_WITH == "X":
        platform_count = MAX_PLATFORM_COUNT
    elif FILL_EMPTY_PLATFORM_NO_DATA_WITH == "N":
        platform_count = MIN_PLATFORM_COUNT
    else:
        platform_count = DEFAULT_PLATFORM_COUNT

    return platform_length, platform_count

def decide_platform_length(min_len, max_len, avg_len):
    if PLATFORM_LENGTH_DECISION_METHOD == "X":
        return min(MAX_PLATFORM_LENGTH, max_len)
    elif PLATFORM_LENGTH_DECISION_METHOD == "N":
        return max(MIN_PLATFORM_LENGTH, min_len)
    elif PLATFORM_LENGTH_DECISION_METHOD == "A":
        return max(MIN_PLATFORM_LENGTH, min(MAX_PLATFORM_LENGTH, avg_len))
    else:
        return DEFAULT_PLATFORM_LENGTH

def validate_master_data(master_df: pd.DataFrame, stations_set: set, logger: logging.Logger) -> None:
    report_lines = []
    error_count = 0

    logger.info("🔎 Starting Stage 00 validation...")

    if master_df.isnull().values.any():
        count = master_df.isnull().sum().sum()
        report_lines.append(f"⚠️ Found {count} missing (NaN) values in master_df.")
        error_count += count

    for idx, row in master_df.iterrows():
        centers = row['center_coordinates']
        if not isinstance(centers, list):
            try:
                centers = json.loads(centers.replace("'", '"'))
            except Exception:
                report_lines.append(f"❌ Row {idx} station {row['station']} has invalid center_coordinates format.")
                error_count += 1
                continue
        if not all(isinstance(c, list) and len(c) == 2 for c in centers):
            report_lines.append(f"❌ Row {idx} station {row['station']} has malformed center_coordinates.")
            error_count += 1

    allowed_line_ids = set(LINE_ID_LIST)
    for idx, row in master_df.iterrows():
        line_ids = row['line_ids']
        if isinstance(line_ids, str):
            line_ids = json.loads(line_ids.replace("'", '"'))
        unexpected = set(line_ids) - allowed_line_ids
        if unexpected:
            report_lines.append(f"❌ Station {row['station']} has unexpected line_ids: {unexpected}")
            error_count += len(unexpected)

    for idx, row in master_df.iterrows():
        connected = row['connected_stations']
        if isinstance(connected, str):
            connected = json.loads(connected.replace("'", '"'))
        for direction in ['West', 'East']:
            unknown_stations = set(connected.get(direction, [])) - stations_set
            if unknown_stations:
                report_lines.append(f"❌ Station {row['station']} has unknown {direction} connections: {unknown_stations}")
                error_count += len(unknown_stations)

    numeric_cols = ['min_platform_length', 'max_platform_length', 'avg_platform_length', 'decided_platform_length', 'platform_count']
    for col in numeric_cols:
        if (master_df[col] < 0).any():
            count = (master_df[col] < 0).sum()
            report_lines.append(f"❌ Column {col} has {count} negative values.")
            error_count += count

    missing_never_skip = set(NEVER_SKIP_LIST) - stations_set
    if missing_never_skip:
        report_lines.append(f"❌ Missing stations from NEVER_SKIP_LIST: {missing_never_skip}")
        error_count += len(missing_never_skip)

    if error_count == 0:
        report_lines.append("✅ Stage 00 validation passed. No critical issues found.")
    else:
        report_lines.append(f"⚠️ Stage 00 validation completed with {error_count} issue(s).")

    for line in report_lines:
        logger.warning(line) if "❌" in line or "⚠️" in line else logger.info(line)

    report_path = PROCESSED_DIR / "stage00_validation_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))
    logger.info(f"📄 Validation report saved to: {report_path.resolve()}")

def run(debug=False):
    logger = setup_logger(debug)
    logger.info("🚀 Stage 00 started: Prepare master station info")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    polygon_df = pd.read_csv(POLYGON_FILE, delimiter=';')
    perron_df = pd.read_csv(PLATFORM_FILE, delimiter=';')

    polygon_df = polygon_df[polygon_df['Linie'].isin(LINE_ID_LIST)].copy()
    stations = set(polygon_df['START_OP']).union(polygon_df['END_OP'])

    master_data = []
    for station in stations:
        station_perron = perron_df[perron_df['Station abbreviation'] == station]
        lengths = station_perron['Length of platform edge'].dropna().tolist()
        if lengths:
            min_len = min(lengths)
            max_len = max(lengths)
            avg_len = sum(lengths) / len(lengths)
            platform_count = len(set(station_perron['Platform number'].dropna()))
        else:
            min_len, max_len, avg_len, platform_count = None, None, None, None

        if min_len is None:
            platform_length, platform_count = get_fallback_values()
            min_len = max_len = avg_len = platform_length
        else:
            platform_length = decide_platform_length(min_len, max_len, avg_len)
            platform_count = max(MIN_PLATFORM_COUNT, min(MAX_PLATFORM_COUNT, platform_count))

        line_ids = sorted(set(
            polygon_df[(polygon_df['START_OP'] == station) | (polygon_df['END_OP'] == station)]['Linie'].tolist()
        ))

        connected_stations = {'West': set(), 'East': set()}
        center_coordinates = set()
        for _, row in polygon_df.iterrows():
            start_op, end_op = row['START_OP'], row['END_OP']
            coords = parse_geo_shape(row['Geo shape'])
            if not coords or len(coords) < 2:
                continue
            if start_op == station:
                connected_stations['East'].add(end_op)
                center_coordinates.add(tuple(coords[0]))
            if end_op == station:
                connected_stations['West'].add(start_op)
                center_coordinates.add(tuple(coords[-1]))

        master_data.append({
            'station': station,
            'min_platform_length': min_len,
            'max_platform_length': max_len,
            'avg_platform_length': avg_len,
            'decided_platform_length': platform_length,
            'platform_count': platform_count,
            'line_ids': line_ids,
            'connected_stations': {k: list(v) for k, v in connected_stations.items()},
            'center_coordinates': [list(c) for c in center_coordinates]
        })

    master_df = pd.DataFrame(master_data)
    master_df['connected_stations'] = master_df['connected_stations'].apply(json.dumps)

    master_df.to_csv(STATION_MASTER_FILE, index=False, encoding='utf-8-sig')
    logger.info(f"✅ Saved master station info to: {STATION_MASTER_FILE.resolve()}")

    # Run validation
    validate_master_data(master_df, stations, logger)
