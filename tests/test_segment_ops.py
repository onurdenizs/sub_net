from utils.segment_ops import calculate_linestring_length, parse_geo_shape

def test_calculate_linestring_length_basic():
    coords = [[0, 0], [3, 4]]  # 3-4-5 üçgeni
    result = calculate_linestring_length(coords)
    assert round(result, 2) == 5.0

def test_parse_geo_shape_valid():
    geo_str = '{"type": "LineString", "coordinates": [[0,0], [1,1]]}'
    coords = parse_geo_shape(geo_str)
    assert coords == [[0,0], [1,1]]

def test_parse_geo_shape_invalid():
    geo_str = 'INVALID_STRING'
    coords = parse_geo_shape(geo_str)
    assert coords == []
