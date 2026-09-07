from backend.repositories.base import clamp_query_window
from backend.services.weather_engine import WeatherEngine, _cached_fire_weather_index


def test_query_window_clamps_expensive_limits():
    skip, limit = clamp_query_window(skip=-20, limit=10_000)

    assert skip == 0
    assert limit == 500


def test_query_window_uses_default_limit_when_missing():
    skip, limit = clamp_query_window(skip=25, limit=None)

    assert skip == 25
    assert limit == 100


def test_fire_weather_index_uses_cached_normalized_inputs():
    _cached_fire_weather_index.cache_clear()
    engine = WeatherEngine()

    first = engine.calculate_fire_weather_index(42.001, 16.001, 38.001, 0.001)
    second = engine.calculate_fire_weather_index(42.002, 16.002, 38.002, 0.002)
    cache_info = _cached_fire_weather_index.cache_info()

    assert first == second
    assert cache_info.hits >= 1
