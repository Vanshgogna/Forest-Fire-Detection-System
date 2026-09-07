from functools import lru_cache


@lru_cache(maxsize=2048)
def _cached_fire_weather_index(temperature: float, humidity: float, wind_speed: float, rainfall: float) -> float:
    heat = temperature * 0.8
    dryness = (100 - humidity) * 0.35
    wind = wind_speed * 0.6
    rain_relief = rainfall * 2.0
    return round(max(0, min(100, heat + dryness + wind - rain_relief)), 2)


def _rounded_weather_inputs(temperature: float, humidity: float, wind_speed: float, rainfall: float) -> tuple[float, float, float, float]:
    return (round(temperature, 2), round(humidity, 2), round(wind_speed, 2), round(rainfall, 2))


def _number_or_default(value: object, default: float) -> float:
    return default if value is None else float(value)


class WeatherEngine:
    def calculate_fire_weather_index(self, temperature: float, humidity: float, wind_speed: float, rainfall: float) -> float:
        return _cached_fire_weather_index(*_rounded_weather_inputs(temperature, humidity, wind_speed, rainfall))

    def summarize(self, record: dict) -> str:
        fwi = self.calculate_fire_weather_index(
            record.get("temperature", 0), record.get("humidity", 0), record.get("wind_speed", 0), record.get("rainfall", 0)
        )
        if fwi >= 80:
            return "Extreme fire weather: heat, dry air, and wind require immediate monitoring."
        if fwi >= 60:
            return "High fire weather: conditions can support rapid ignition and spread."
        return "Weather risk is currently manageable but should continue to be monitored."

    def alert_flags(self, record: dict) -> list[str]:
        flags = []
        temperature = _number_or_default(record.get("temperature"), 0)
        humidity = _number_or_default(record.get("humidity"), 100)
        wind_speed = _number_or_default(record.get("wind_speed", record.get("wind")), 0)
        rainfall = _number_or_default(record.get("rainfall"), 0)
        uv_index = _number_or_default(record.get("uv_index"), 0)
        if temperature >= 40:
            flags.append("high_temperature")
        if humidity <= 20:
            flags.append("low_humidity")
        if wind_speed >= 35:
            flags.append("strong_wind")
        if rainfall <= 0.2:
            flags.append("low_rainfall")
        if uv_index >= 9:
            flags.append("high_uv")
        return flags

    def historical_trend(self, records: list[dict]) -> dict:
        if not records:
            return {"records": 0, "trend": "insufficient_data"}
        fire_weather_values = [
            self.calculate_fire_weather_index(item.get("temperature", 0), item.get("humidity", 0), item.get("wind_speed", 0), item.get("rainfall", 0))
            for item in records
        ]
        average_fwi = round(
            sum(fire_weather_values) / len(fire_weather_values),
            2,
        )
        return {
            "records": len(records),
            "average_fire_weather_index": average_fwi,
            "trend": "rising" if records[-1].get("temperature", 0) >= records[0].get("temperature", 0) else "cooling",
        }
