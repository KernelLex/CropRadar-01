"""
weather_service.py - Weather data fetching for CropRadar predictive risk.

Uses Open-Meteo API (free, no API key required) to get current weather
and recent weather history for risk scoring.
https://open-meteo.com/
"""

import logging
from typing import Optional

import requests

import database

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Cache TTL: reuse weather data for same grid cell within this window
CACHE_TTL_HOURS = 6


def get_weather_features(lat: float, lon: float) -> Optional[dict]:
    """
    Fetch weather features for a location. Uses DB cache first, then API.
    Returns dict with normalized weather features, or None on failure.
    """
    grid_id = database.lat_lon_to_grid_id(lat, lon)

    # Check cache first
    cached = database.get_recent_weather_snapshot(grid_id, max_age_hours=CACHE_TTL_HOURS)
    if cached:
        logger.info("Weather cache hit for grid %s", grid_id)
        return {
            "temperature_mean": cached["temperature_mean"],
            "humidity_mean": cached["humidity_mean"],
            "precipitation_sum": cached["precipitation_sum"],
            "wind_speed_mean": cached["wind_speed_mean"],
            "dew_point": cached["dew_point"],
            "cloud_cover": cached["cloud_cover"],
            "source": cached["source"],
            "cached": True,
        }

    try:
        features = _fetch_from_open_meteo(lat, lon)
        if features:
            database.save_weather_snapshot(grid_id, lat, lon, features)
            logger.info("Weather fetched and cached for grid %s", grid_id)
        return features
    except Exception as exc:
        logger.warning("Weather API error: %s", exc)
        return None


def _fetch_from_open_meteo(lat: float, lon: float) -> Optional[dict]:
    """
    Fetch current weather + last 7 days summary from Open-Meteo.
    No API key required.
    """
    resp = requests.get(
        OPEN_METEO_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "wind_speed_10m",
                "cloud_cover",
                "dew_point_2m",
            ]),
            "daily": ",".join([
                "temperature_2m_mean",
                "precipitation_sum",
                "wind_speed_10m_max",
            ]),
            "past_days": 7,
            "forecast_days": 1,
            "timezone": "auto",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    current = data.get("current", {})
    daily = data.get("daily", {})

    # Current values
    temperature = current.get("temperature_2m", 0)
    humidity = current.get("relative_humidity_2m", 0)
    wind_speed = current.get("wind_speed_10m", 0)
    cloud_cover = current.get("cloud_cover", 0)
    dew_point = current.get("dew_point_2m")
    current_precip = current.get("precipitation", 0)

    # Sum precipitation over last 7 days from daily data
    daily_precip = daily.get("precipitation_sum", [])
    precip_7d = sum(p for p in daily_precip if p is not None)

    # Average temperature over last 7 days
    daily_temps = daily.get("temperature_2m_mean", [])
    valid_temps = [t for t in daily_temps if t is not None]
    avg_temp_7d = sum(valid_temps) / len(valid_temps) if valid_temps else temperature

    # Dew point fallback: approximate if not provided
    if dew_point is None:
        dew_point = round(temperature - (100 - humidity) / 5, 1)

    return {
        "temperature_mean": round(avg_temp_7d, 1),
        "humidity_mean": round(humidity, 1),
        "precipitation_sum": round(precip_7d, 2),
        "wind_speed_mean": round(wind_speed, 1),
        "dew_point": round(dew_point, 1),
        "cloud_cover": round(cloud_cover, 1),
        "source": "open-meteo",
        "cached": False,
    }


def get_recent_weather_summary(lat: float, lon: float, days: int = 7) -> Optional[dict]:
    """
    Convenience wrapper returning weather features.
    Open-Meteo already includes past_days data so this uses the same call.
    """
    return get_weather_features(lat, lon)
