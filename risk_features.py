"""
risk_features.py - Feature engineering for CropRadar predictive risk.

Combines weather, NDVI, and local disease context into a single
structured feature dictionary for risk scoring.
"""

import logging
from collections import Counter
from typing import Optional

import database
import weather_service
import satellite_service

logger = logging.getLogger(__name__)


def build_risk_features(lat: float, lon: float) -> dict:
    """
    Build a combined feature dictionary from multiple data sources.

    Returns a dict with keys grouped by source:
      - location: grid_id, lat, lon
      - weather: temperature_mean, humidity_mean, precipitation_sum, etc.
      - ndvi: ndvi_mean, ndvi_change_7d, stress_flag, etc.
      - disease_context: nearby_disease_count, nearby_outbreak_count,
                         disease_distribution, etc.
    """
    grid_id = database.lat_lon_to_grid_id(lat, lon)

    features = {
        "grid_id": grid_id,
        "lat": lat,
        "lon": lon,
        # Flags for which data sources were available
        "has_weather": False,
        "has_ndvi": False,
        "has_disease_history": False,
    }

    # --- Weather features ---
    weather = weather_service.get_weather_features(lat, lon)
    if weather:
        features["has_weather"] = True
        features["temperature_mean"] = weather.get("temperature_mean")
        features["humidity_mean"] = weather.get("humidity_mean")
        features["precipitation_sum"] = weather.get("precipitation_sum")
        features["wind_speed_mean"] = weather.get("wind_speed_mean")
        features["dew_point"] = weather.get("dew_point")
        features["cloud_cover"] = weather.get("cloud_cover")
    else:
        features["temperature_mean"] = None
        features["humidity_mean"] = None
        features["precipitation_sum"] = None
        features["wind_speed_mean"] = None
        features["dew_point"] = None
        features["cloud_cover"] = None

    # --- NDVI features ---
    ndvi = satellite_service.get_ndvi_features(lat, lon)
    if ndvi:
        features["has_ndvi"] = True
        features["ndvi_mean"] = ndvi.get("ndvi_mean")
        features["ndvi_change_7d"] = ndvi.get("ndvi_change_7d")
        features["ndvi_change_14d"] = ndvi.get("ndvi_change_14d")
        features["stress_flag"] = ndvi.get("stress_flag", False)
    else:
        features["ndvi_mean"] = None
        features["ndvi_change_7d"] = None
        features["ndvi_change_14d"] = None
        features["stress_flag"] = False

    # --- Disease context (from existing database) ---
    try:
        nearby_reports = database.get_nearby_disease_history(
            lat, lon, radius_km=50, hours=168,  # 7 days
        )
        features["has_disease_history"] = len(nearby_reports) > 0
        features["nearby_disease_count"] = len(nearby_reports)

        # Disease type distribution
        disease_counts = Counter(r["disease_type"] for r in nearby_reports)
        features["disease_distribution"] = dict(disease_counts)
        features["dominant_diseases"] = [
            d for d, _ in disease_counts.most_common(3)
        ]

        # Outbreaks (existing logic reuse)
        outbreaks = database.get_nearby_outbreak_risk(
            lat, lon, radius_km=50, threshold=3, hours=48,
        )
        features["nearby_outbreak_count"] = len(outbreaks)
        features["outbreak_diseases"] = [o["disease_type"] for o in outbreaks]

    except Exception as exc:
        logger.warning("Failed to get disease context: %s", exc)
        features["nearby_disease_count"] = 0
        features["disease_distribution"] = {}
        features["dominant_diseases"] = []
        features["nearby_outbreak_count"] = 0
        features["outbreak_diseases"] = []

    return features
