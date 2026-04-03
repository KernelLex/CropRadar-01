"""
risk_model.py - Rule-based crop disease risk scoring engine for CropRadar.

Scoring breakdown (100 points total):
  - Weather favorability: 0–35 points
  - NDVI vegetation stress: 0–25 points
  - Disease history / context: 0–40 points

Risk levels:
  Low    : 0–30
  Medium : 31–60
  High   : 61–100
"""

import logging
from typing import Optional

import database

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Disease ↔ weather correlation rules
# ---------------------------------------------------------------------------

DISEASE_WEATHER_PROFILES = {
    "Late Blight": {
        "temp_range": (15, 22),
        "humidity_min": 90,
        "rain_favorable": True,
        "crops": ["Tomato", "Potato"],
    },
    "Powdery Mildew": {
        "temp_range": (20, 30),
        "humidity_range": (40, 70),
        "rain_favorable": False,
        "crops": ["Cucumber", "Squash", "Grapes", "Wheat"],
    },
    "Leaf Spot": {
        "temp_range": (22, 30),
        "humidity_min": 80,
        "rain_favorable": True,
        "crops": ["Tomato", "Pepper", "Cotton", "Maize"],
    },
    "Rust": {
        "temp_range": (15, 25),
        "humidity_min": 80,
        "rain_favorable": True,
        "crops": ["Wheat", "Soybean", "Coffee", "Bean"],
    },
    "Leaf Blight": {
        "temp_range": (25, 35),
        "humidity_min": 85,
        "rain_favorable": True,
        "crops": ["Rice", "Maize", "Sorghum"],
    },
    "Downy Mildew": {
        "temp_range": (15, 23),
        "humidity_min": 85,
        "rain_favorable": True,
        "crops": ["Grapes", "Cucumber", "Sunflower"],
    },
    "Anthracnose": {
        "temp_range": (20, 30),
        "humidity_min": 80,
        "rain_favorable": True,
        "crops": ["Mango", "Chili", "Bean", "Papaya"],
    },
}

# Crops common in Indian agriculture (for general prediction)
COMMON_CROPS = ["Rice", "Wheat", "Tomato", "Potato", "Maize", "Cotton", "Sorghum"]


def score_area_risk(features: dict) -> dict:
    """
    Score the disease risk for an area based on combined features.

    Args:
        features: dict from risk_features.build_risk_features()

    Returns:
        dict with: risk_score, risk_level, likely_crops_at_risk,
                   likely_diseases, reasons, recommendations
    """
    weather_score, weather_reasons = _score_weather(features)
    ndvi_score, ndvi_reasons = _score_ndvi(features)
    disease_score, disease_reasons = _score_disease_context(features)

    total_score = weather_score + ndvi_score + disease_score
    total_score = min(100, max(0, total_score))

    risk_level = _score_to_level(total_score)
    reasons = weather_reasons + ndvi_reasons + disease_reasons

    # Determine likely diseases and crops at risk
    likely_diseases = _identify_likely_diseases(features)
    likely_crops = _identify_crops_at_risk(likely_diseases, features)

    recommendations = _generate_recommendations(risk_level, likely_diseases)

    result = {
        "risk_score": round(total_score, 1),
        "risk_level": risk_level,
        "likely_crops_at_risk": likely_crops,
        "likely_diseases": likely_diseases,
        "reasons": reasons,
        "recommendations": recommendations,
        "score_breakdown": {
            "weather": weather_score,
            "ndvi": ndvi_score,
            "disease_context": disease_score,
        },
        "grid_id": features.get("grid_id"),
        "lat": features.get("lat"),
        "lon": features.get("lon"),
    }

    # Save to DB for caching and history
    try:
        database.save_risk_score(
            grid_id=features.get("grid_id", ""),
            lat=features.get("lat", 0),
            lon=features.get("lon", 0),
            risk_data=result,
        )
    except Exception as exc:
        logger.warning("Failed to save risk score: %s", exc)

    return result


def _score_to_level(score: float) -> str:
    if score <= 30:
        return "Low"
    elif score <= 60:
        return "Medium"
    else:
        return "High"


# ---------------------------------------------------------------------------
# Weather scoring (0–35 points)
# ---------------------------------------------------------------------------

def _score_weather(features: dict) -> tuple[float, list[str]]:
    if not features.get("has_weather"):
        return 0, []

    score = 0.0
    reasons = []

    temp = features.get("temperature_mean")
    humidity = features.get("humidity_mean")
    precip = features.get("precipitation_sum")
    wind = features.get("wind_speed_mean")

    # High humidity is the single most important disease driver
    if humidity is not None:
        if humidity >= 90:
            score += 15
            reasons.append("Very high humidity (≥90%) — strongly favors fungal diseases")
        elif humidity >= 80:
            score += 10
            reasons.append("High humidity (≥80%) — favors disease spread")
        elif humidity >= 70:
            score += 5
            reasons.append("Moderate humidity — some disease risk")

    # Temperature in disease-favorable range (20-30°C covers most pathogens)
    if temp is not None:
        if 20 <= temp <= 30:
            score += 8
            reasons.append(f"Temperature ({temp}°C) in optimal range for many pathogens")
        elif 15 <= temp < 20 or 30 < temp <= 35:
            score += 4
            reasons.append(f"Temperature ({temp}°C) moderately favorable for some diseases")

    # Recent precipitation increases disease risk
    if precip is not None:
        if precip > 20:
            score += 8
            reasons.append(f"Significant recent rainfall ({precip:.1f}mm) — increases disease spread")
        elif precip > 5:
            score += 4
            reasons.append(f"Moderate rainfall ({precip:.1f}mm) — may increase disease risk")

    # Low wind = poor air circulation = higher disease risk
    if wind is not None:
        if wind < 2:
            score += 4
            reasons.append("Very low wind speed — poor air circulation favors pathogens")
        elif wind < 5:
            score += 2

    return min(35, score), reasons


# ---------------------------------------------------------------------------
# NDVI scoring (0–25 points)
# ---------------------------------------------------------------------------

def _score_ndvi(features: dict) -> tuple[float, list[str]]:
    if not features.get("has_ndvi"):
        return 0, []

    score = 0.0
    reasons = []

    ndvi = features.get("ndvi_mean")
    change_7d = features.get("ndvi_change_7d")
    change_14d = features.get("ndvi_change_14d")
    stress = features.get("stress_flag", False)

    # Declining NDVI = vegetation stress
    if change_7d is not None and change_7d < -0.05:
        score += 12
        reasons.append("NDVI declining rapidly — vegetation stress detected in recent days")
    elif change_7d is not None and change_7d < -0.02:
        score += 6
        reasons.append("NDVI declining slightly — possible early vegetation stress")

    # 14-day trend
    if change_14d is not None and change_14d < -0.08:
        score += 5
        reasons.append("Sustained vegetation decline over 2 weeks")

    # Low absolute NDVI
    if ndvi is not None:
        if ndvi < 0.2:
            score += 8
            reasons.append("Very low vegetation health index — significant crop stress")
        elif ndvi < 0.35:
            score += 4
            reasons.append("Below-average vegetation health index")

    # Stress flag direct
    if stress and score < 10:
        score += 5
        reasons.append("Vegetation stress indicators detected")

    return min(25, score), reasons


# ---------------------------------------------------------------------------
# Disease context scoring (0–40 points)
# ---------------------------------------------------------------------------

def _score_disease_context(features: dict) -> tuple[float, list[str]]:
    score = 0.0
    reasons = []

    nearby_count = features.get("nearby_disease_count", 0)
    outbreak_count = features.get("nearby_outbreak_count", 0)
    disease_dist = features.get("disease_distribution", {})

    # Recent nearby disease reports
    if nearby_count >= 10:
        score += 20
        reasons.append(f"{nearby_count} disease reports nearby in last 7 days — high local activity")
    elif nearby_count >= 5:
        score += 12
        reasons.append(f"{nearby_count} disease reports nearby in last 7 days")
    elif nearby_count >= 2:
        score += 6
        reasons.append(f"{nearby_count} disease reports nearby — early warning")
    elif nearby_count >= 1:
        score += 3
        reasons.append("Recent disease activity reported nearby")

    # Active outbreaks nearby
    if outbreak_count >= 2:
        score += 15
        reasons.append(f"{outbreak_count} active outbreaks nearby — significant spread risk")
    elif outbreak_count >= 1:
        score += 10
        reasons.append("Active outbreak detected nearby — elevated risk")

    # Disease diversity (multiple diseases = stressed ecosystem)
    num_disease_types = len(disease_dist)
    if num_disease_types >= 3:
        score += 5
        reasons.append(f"{num_disease_types} different diseases reported nearby — broad risk")
    elif num_disease_types >= 2:
        score += 2

    return min(40, score), reasons


# ---------------------------------------------------------------------------
# Disease & crop identification
# ---------------------------------------------------------------------------

def _identify_likely_diseases(features: dict) -> list[str]:
    """Identify which diseases are most likely given the conditions."""
    likely = []

    # Start with diseases already reported nearby
    dominant = features.get("dominant_diseases", [])
    likely.extend(dominant)

    # Add weather-correlated diseases
    if features.get("has_weather"):
        temp = features.get("temperature_mean")
        humidity = features.get("humidity_mean")

        if temp is not None and humidity is not None:
            for disease, profile in DISEASE_WEATHER_PROFILES.items():
                if disease in likely:
                    continue
                t_lo, t_hi = profile.get("temp_range", (0, 100))
                h_min = profile.get("humidity_min", 0)
                h_range = profile.get("humidity_range")

                temp_match = t_lo <= temp <= t_hi
                if h_range:
                    humidity_match = h_range[0] <= humidity <= h_range[1]
                else:
                    humidity_match = humidity >= h_min

                if temp_match and humidity_match:
                    likely.append(disease)

    # Deduplicate and limit
    seen = set()
    result = []
    for d in likely:
        if d not in seen and d != "Healthy Leaf":
            seen.add(d)
            result.append(d)
    return result[:5]


def _identify_crops_at_risk(likely_diseases: list[str], features: dict) -> list[str]:
    """Determine which crops may be at risk based on likely diseases."""
    crops = set()
    for disease in likely_diseases:
        profile = DISEASE_WEATHER_PROFILES.get(disease)
        if profile:
            crops.update(profile.get("crops", []))

    if not crops:
        # Fallback: common crops in the region
        crops = set(COMMON_CROPS[:4])

    return sorted(crops)[:6]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def _generate_recommendations(risk_level: str, likely_diseases: list[str]) -> list[str]:
    """Generate actionable recommendations based on risk level."""
    recs = []

    if risk_level == "High":
        recs.append("Inspect all fields daily for early disease symptoms")
        recs.append("Begin preventive fungicide/treatment application if not already done")
        recs.append("Isolate any suspicious or symptomatic plants immediately")
        recs.append("Improve drainage and airflow between rows")
        recs.append("Avoid overhead irrigation — use drip irrigation if possible")
    elif risk_level == "Medium":
        recs.append("Monitor crops closely every 2–3 days")
        recs.append("Prepare preventive treatments and have supplies ready")
        recs.append("Ensure proper spacing for good air circulation")
        recs.append("Remove weeds and debris that may harbor pathogens")
    else:
        recs.append("Continue regular crop monitoring as usual")
        recs.append("Maintain good agricultural practices")
        recs.append("Keep fields clean and well-drained")

    # Disease-specific tips
    if "Late Blight" in likely_diseases:
        recs.append("Late Blight risk: avoid watering foliage, apply copper-based sprays")
    if "Powdery Mildew" in likely_diseases:
        recs.append("Powdery Mildew risk: ensure sunlight exposure, use sulfur-based treatments")
    if "Rust" in likely_diseases:
        recs.append("Rust risk: remove infected leaves promptly, apply triazole fungicide")

    return recs
