import pytest
from utils.platform_ops import (
    get_fallback_values,
    decide_platform_length,
    find_direction_between_coordinates
)
from utils.constants import (
    MAX_PLATFORM_LENGTH, MIN_PLATFORM_LENGTH, DEFAULT_PLATFORM_LENGTH,
    FILL_EMPTY_PLATFORM_LENGTH_DATA_WITH, FILL_EMPTY_PLATFORM_NO_DATA_WITH,
    PLATFORM_LENGTH_DECISION_METHOD
)

def test_get_fallback_values():
    length, count = get_fallback_values()
    assert isinstance(length, (int, float))
    assert isinstance(count, int)
    assert length in [MIN_PLATFORM_LENGTH, MAX_PLATFORM_LENGTH, DEFAULT_PLATFORM_LENGTH]

def test_decide_platform_length_X(monkeypatch):
    monkeypatch.setattr('utils.platform_ops.PLATFORM_LENGTH_DECISION_METHOD', 'X')
    result = decide_platform_length(100, 400, 300)
    assert result == min(MAX_PLATFORM_LENGTH, 400)

def test_decide_platform_length_N(monkeypatch):
    monkeypatch.setattr('utils.platform_ops.PLATFORM_LENGTH_DECISION_METHOD', 'N')
    result = decide_platform_length(100, 400, 300)
    assert result == max(MIN_PLATFORM_LENGTH, 100)

def test_decide_platform_length_A(monkeypatch):
    monkeypatch.setattr('utils.platform_ops.PLATFORM_LENGTH_DECISION_METHOD', 'A')
    result = decide_platform_length(100, 400, 300)
    assert isinstance(result, (int, float))

def test_find_direction_between_coordinates():
    assert find_direction_between_coordinates([0, 0], [1, 0]) == "East"
    assert find_direction_between_coordinates([1, 0], [0, 0]) == "West"
    assert find_direction_between_coordinates([1, 0], [1, 5]) == "Same"
