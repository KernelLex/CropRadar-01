"""
satellite_service.py - NDVI / vegetation health service for CropRadar.

For MVP, this uses a season-and-weather-based vegetation stress estimator
that produces realistic NDVI-like signals. The module structure is ready
for plugging in real satellite data (NASA AppEEARS, Sentinel Hub, etc.)
in a future version.

NDVI (Normalized Difference Vegetation Index) ranges:
  -1.0 to 0.0  : water / bare soil / non-vegetated
   0.0 to 0.2  : sparse vegetation / stressed
   0.2 to 0.5  : moderate vegetation
   0.5 to 0.8  : dense healthy vegetation
   0.8 to 1.0  : very dense healthy vegetation
"""

import logging
import math
from datetime import datetime
from typing import Optional

import database

logger = logging.getLogger(__name__)

# Cache TTL: reuse NDVI data for same grid cell within this window
CACHE_TTL_HOURS = 24


def get_ndvi_features(lat: float, lon: float) -> Optional[dict]:
    """
    Get NDVI / vegetation health features for a location.
    Uses DB cache first, then synthetic estimation.
    Returns dict with NDVI features, or None on failure.
    """
    grid_id = database.lat_lon_to_grid_id(lat, lon)

    # Check cache first
    cached = database.get_recent_ndvi_snapshot(grid_id, max_age_hours=CACHE_TTL_HOURS)
    if cached:
        logger.info("NDVI cache hit for grid %s", grid_id)
        return {
            "ndvi_mean": cached["ndvi_mean"],
            "ndvi_change_7d": cached["ndvi_change_7d"],
            "ndvi_change_14d": cached["ndvi_change_14d"],
            "stress_flag": _is_stressed(cached["ndvi_mean"], cached["ndvi_change_7d"]),
            "source": cached["source"],
            "cached": True,
        }

    try:
        features = _estimate_ndvi_synthetic(lat, lon)
        if features:
            database.save_ndvi_snapshot(grid_id, lat, lon, features)
            logger.info("NDVI estimated and cached for grid %s", grid_id)
        return features
    except Exception as exc:
        logger.warning("NDVI estimation error: %s", exc)
        return None


def _estimate_ndvi_synthetic(lat: float, lon: float) -> dict:
    """
    Generate a synthetic NDVI estimate based on:
    - Season (month of year → vegetation growth cycle)
    - Latitude (tropical vs temperate vegetation patterns)
    - Recent weather data if available (drought/excess rain stress)

    This is a heuristic for MVP — NOT real satellite data.
    Replace this function body with real API calls for production.
    """
    now = datetime.utcnow()
    month = now.month
    day_of_year = now.timetuple().tm_yday

    # --- Base NDVI from season + latitude ---
    # Tropical regions (|lat| < 23.5): more stable vegetation year-round
    # Temperate: strong seasonal cycle
    abs_lat = abs(lat)

    if abs_lat < 23.5:
        # Tropical: NDVI ~0.4-0.7, slight monsoon variation
        # Indian monsoon peaks Jun-Sep (months 6-9)
        seasonal_factor = 0.55 + 0.15 * math.sin(
            2 * math.pi * (day_of_year - 90) / 365
        )
    elif abs_lat < 45:
        # Subtropical/temperate: stronger seasonal variation
        seasonal_factor = 0.45 + 0.25 * math.sin(
            2 * math.pi * (day_of_year - 80) / 365
        )
    else:
        # Higher latitudes: large seasonal swing
        seasonal_factor = 0.35 + 0.35 * math.sin(
            2 * math.pi * (day_of_year - 80) / 365
        )

    # Clamp to valid NDVI range
    ndvi_mean = max(0.05, min(0.85, seasonal_factor))

    # --- Simulate 7-day and 14-day NDVI change ---
    # Use weather data if available to modulate change
    grid_id = database.lat_lon_to_grid_id(lat, lon)
    weather = database.get_recent_weather_snapshot(grid_id, max_age_hours=12)

    ndvi_change_7d = 0.0
    ndvi_change_14d = 0.0

    if weather:
        temp = weather.get("temperature_mean") or 25
        humidity = weather.get("humidity_mean") or 60
        precip = weather.get("precipitation_sum") or 0

        # High heat + low humidity = vegetation stress (declining NDVI)
        if temp > 35 and humidity < 40:
            ndvi_change_7d = -0.08
            ndvi_change_14d = -0.12
        # Excessive rain can also stress crops (waterlogging)
        elif precip > 50:
            ndvi_change_7d = -0.05
            ndvi_change_14d = -0.08
        # Good conditions: moderate temp, adequate moisture
        elif 18 <= temp <= 30 and humidity >= 50:
            ndvi_change_7d = 0.02
            ndvi_change_14d = 0.04
        # Dry but not extreme
        elif humidity < 40 and precip < 2:
            ndvi_change_7d = -0.03
            ndvi_change_14d = -0.05
    else:
        # No weather data — use gentle seasonal trend
        # In growing season (spring/summer) slight increase, else decrease
        if month in (3, 4, 5, 6, 7, 8):
            ndvi_change_7d = 0.01
            ndvi_change_14d = 0.02
        elif month in (10, 11, 12):
            ndvi_change_7d = -0.02
            ndvi_change_14d = -0.04
        else:
            ndvi_change_7d = 0.0
            ndvi_change_14d = 0.01

    # Round values
    ndvi_mean = round(ndvi_mean, 3)
    ndvi_change_7d = round(ndvi_change_7d, 3)
    ndvi_change_14d = round(ndvi_change_14d, 3)

    stress_flag = _is_stressed(ndvi_mean, ndvi_change_7d)

    return {
        "ndvi_mean": ndvi_mean,
        "ndvi_change_7d": ndvi_change_7d,
        "ndvi_change_14d": ndvi_change_14d,
        "stress_flag": stress_flag,
        "source": "synthetic-seasonal",
        "cached": False,
    }


def _is_stressed(ndvi_mean: Optional[float], ndvi_change_7d: Optional[float]) -> bool:
    """Determine if vegetation is under stress based on NDVI values."""
    if ndvi_mean is None:
        return False
    if ndvi_mean < 0.25:
        return True
    if ndvi_change_7d is not None and ndvi_change_7d < -0.05:
        return True
    return False


def get_ndvi_trend(lat: float, lon: float, days: int = 14) -> Optional[dict]:
    """Convenience wrapper matching the spec. Returns same as get_ndvi_features."""
    return get_ndvi_features(lat, lon)
