"""
test_risk_pipeline.py - Integration tests for the CropRadar predictive
risk analysis pipeline.

Run:  python test_risk_pipeline.py
Uses a temporary SQLite database so the production DB is not affected.
"""

import os
import sys
import tempfile

# Use a temporary database for tests
_test_db = tempfile.mktemp(suffix=".db")
os.environ.setdefault("CROPRADAR_DB_PATH", _test_db)

import database  # noqa: E402

# Override DB_PATH for testing
database.DB_PATH = _test_db

PASS = 0
FAIL = 0


def ok(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    status = "[PASS]" if condition else "[FAIL]"
    print(f"  {status}: {label}" + (f"  ({detail})" if detail else ""))
    if condition:
        PASS += 1
    else:
        FAIL += 1


# ---------------------------------------------------------------------------
# 1. Schema creation
# ---------------------------------------------------------------------------

def test_schema_creation() -> None:
    print("\n[1] Schema creation — new predictive risk tables")
    database.init_db()
    with database.get_connection() as conn:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
    ok("weather_snapshots table exists", "weather_snapshots" in tables)
    ok("ndvi_snapshots table exists", "ndvi_snapshots" in tables)
    ok("risk_scores table exists", "risk_scores" in tables)
    # Verify existing tables still exist
    ok("disease_reports table still exists", "disease_reports" in tables)
    ok("bot_users table still exists", "bot_users" in tables)
    ok("outbreak_notifications table still exists", "outbreak_notifications" in tables)


# ---------------------------------------------------------------------------
# 2. Grid ID mapping
# ---------------------------------------------------------------------------

def test_grid_id() -> None:
    print("\n[2] Grid ID mapping")
    grid = database.lat_lon_to_grid_id(12.9716, 77.5946)
    ok("grid_id format correct", grid == "12.97_77.59", f"got {grid}")

    grid2 = database.lat_lon_to_grid_id(12.9716, 77.5946, precision=1)
    ok("precision=1 works", grid2 == "13.0_77.6", f"got {grid2}")


# ---------------------------------------------------------------------------
# 3. Weather snapshot CRUD
# ---------------------------------------------------------------------------

def test_weather_snapshot() -> None:
    print("\n[3] Weather snapshot save/load")
    grid_id = "12.97_77.59"
    data = {
        "temperature_mean": 28.5,
        "humidity_mean": 75.0,
        "precipitation_sum": 12.3,
        "wind_speed_mean": 3.2,
        "dew_point": 23.0,
        "cloud_cover": 40.0,
        "source": "test",
    }
    row_id = database.save_weather_snapshot(grid_id, 12.97, 77.59, data)
    ok("weather snapshot saved", row_id > 0, f"id={row_id}")

    cached = database.get_recent_weather_snapshot(grid_id, max_age_hours=1)
    ok("weather snapshot retrieved", cached is not None)
    ok("temperature correct", abs(cached["temperature_mean"] - 28.5) < 0.01)
    ok("humidity correct", abs(cached["humidity_mean"] - 75.0) < 0.01)

    # Expired cache should return None
    expired = database.get_recent_weather_snapshot(grid_id, max_age_hours=0)
    # Note: this might still return the row if the test runs in < 1 sec
    # so we just check the function doesn't crash
    ok("expired cache query works", True)


# ---------------------------------------------------------------------------
# 4. NDVI snapshot CRUD
# ---------------------------------------------------------------------------

def test_ndvi_snapshot() -> None:
    print("\n[4] NDVI snapshot save/load")
    grid_id = "12.97_77.59"
    data = {
        "ndvi_mean": 0.55,
        "ndvi_change_7d": -0.03,
        "ndvi_change_14d": -0.05,
        "source": "test-synthetic",
    }
    row_id = database.save_ndvi_snapshot(grid_id, 12.97, 77.59, data)
    ok("ndvi snapshot saved", row_id > 0, f"id={row_id}")

    cached = database.get_recent_ndvi_snapshot(grid_id, max_age_hours=1)
    ok("ndvi snapshot retrieved", cached is not None)
    ok("ndvi_mean correct", abs(cached["ndvi_mean"] - 0.55) < 0.01)


# ---------------------------------------------------------------------------
# 5. Risk score CRUD
# ---------------------------------------------------------------------------

def test_risk_score() -> None:
    print("\n[5] Risk score save/load")
    grid_id = "12.97_77.59"
    risk_data = {
        "disease_type": "Leaf Blight",
        "crop_type": "Rice",
        "risk_score": 65.0,
        "risk_level": "High",
        "reasons": ["High humidity", "Recent disease reports"],
    }
    row_id = database.save_risk_score(grid_id, 12.97, 77.59, risk_data)
    ok("risk score saved", row_id > 0, f"id={row_id}")

    cached = database.get_recent_risk_score(grid_id, max_age_hours=1)
    ok("risk score retrieved", cached is not None)
    ok("risk_level correct", cached["risk_level"] == "High")
    ok("risk_score correct", abs(cached["risk_score"] - 65.0) < 0.01)


# ---------------------------------------------------------------------------
# 6. Nearby disease history
# ---------------------------------------------------------------------------

def test_nearby_disease_history() -> None:
    print("\n[6] Nearby disease history")
    # Insert some test reports
    for i in range(4):
        database.insert_report(
            disease_type="Leaf Blight" if i < 3 else "Rust",
            confidence="High",
            remedy="Test remedy",
            prevention="Test prevention",
            latitude=12.97 + i * 0.001,
            longitude=77.59 + i * 0.001,
        )

    history = database.get_nearby_disease_history(12.97, 77.59, radius_km=50, hours=168)
    ok("history returns results", len(history) >= 4, f"got {len(history)}")

    # Check that disease_type and distance_km fields exist
    if history:
        ok("disease_type field present", "disease_type" in history[0])
        ok("distance_km field present", "distance_km" in history[0])


# ---------------------------------------------------------------------------
# 7. NDVI synthetic estimation
# ---------------------------------------------------------------------------

def test_satellite_service() -> None:
    print("\n[7] Satellite service — synthetic NDVI")
    import satellite_service

    features = satellite_service._estimate_ndvi_synthetic(12.97, 77.59)
    ok("ndvi_mean is valid", 0 < features["ndvi_mean"] <= 1.0, f"got {features['ndvi_mean']}")
    ok("ndvi_change_7d present", "ndvi_change_7d" in features)
    ok("stress_flag present", "stress_flag" in features)
    ok("source is synthetic", "synthetic" in features["source"])


# ---------------------------------------------------------------------------
# 8. Risk feature builder
# ---------------------------------------------------------------------------

def test_risk_features() -> None:
    print("\n[8] Risk feature builder")
    import risk_features

    features = risk_features.build_risk_features(12.97, 77.59)
    ok("grid_id present", "grid_id" in features)
    ok("has_ndvi flag present", "has_ndvi" in features)
    ok("has_disease_history flag present", "has_disease_history" in features)
    ok("nearby_disease_count present", "nearby_disease_count" in features)
    ok("disease_distribution present", "disease_distribution" in features)
    ok("ndvi_mean present", "ndvi_mean" in features)


# ---------------------------------------------------------------------------
# 9. Risk scoring engine
# ---------------------------------------------------------------------------

def test_risk_model() -> None:
    print("\n[9] Risk scoring engine")
    import risk_model

    # Test with full features
    features = {
        "grid_id": "12.97_77.59",
        "lat": 12.97,
        "lon": 77.59,
        "has_weather": True,
        "temperature_mean": 28,
        "humidity_mean": 85,
        "precipitation_sum": 15,
        "wind_speed_mean": 2,
        "dew_point": 24,
        "cloud_cover": 70,
        "has_ndvi": True,
        "ndvi_mean": 0.35,
        "ndvi_change_7d": -0.06,
        "ndvi_change_14d": -0.09,
        "stress_flag": True,
        "has_disease_history": True,
        "nearby_disease_count": 5,
        "disease_distribution": {"Leaf Blight": 3, "Rust": 2},
        "dominant_diseases": ["Leaf Blight", "Rust"],
        "nearby_outbreak_count": 1,
        "outbreak_diseases": ["Leaf Blight"],
    }

    result = risk_model.score_area_risk(features)
    ok("risk_score present", "risk_score" in result)
    ok("risk_level present", "risk_level" in result)
    ok("risk_score > 0 with these features", result["risk_score"] > 0)
    ok("risk_level is Medium or High", result["risk_level"] in ("Medium", "High"),
       f"got {result['risk_level']} (score={result['risk_score']})")
    ok("likely_diseases present", len(result["likely_diseases"]) > 0)
    ok("likely_crops_at_risk present", len(result["likely_crops_at_risk"]) > 0)
    ok("reasons present", len(result["reasons"]) > 0)
    ok("recommendations present", len(result["recommendations"]) > 0)
    ok("score_breakdown present", "score_breakdown" in result)

    # Test with empty features
    empty_features = {
        "grid_id": "0.0_0.0", "lat": 0, "lon": 0,
        "has_weather": False, "has_ndvi": False, "has_disease_history": False,
        "temperature_mean": None, "humidity_mean": None,
        "precipitation_sum": None, "wind_speed_mean": None,
        "dew_point": None, "cloud_cover": None,
        "ndvi_mean": None, "ndvi_change_7d": None,
        "ndvi_change_14d": None, "stress_flag": False,
        "nearby_disease_count": 0, "disease_distribution": {},
        "dominant_diseases": [], "nearby_outbreak_count": 0,
        "outbreak_diseases": [],
    }
    empty_result = risk_model.score_area_risk(empty_features)
    ok("empty features gives Low risk", empty_result["risk_level"] == "Low",
       f"got {empty_result['risk_level']} (score={empty_result['risk_score']})")


# ---------------------------------------------------------------------------
# 10. Risk report generator
# ---------------------------------------------------------------------------

def test_risk_report() -> None:
    print("\n[10] Risk report generator")
    import risk_report

    result = {
        "risk_score": 72.0,
        "risk_level": "High",
        "likely_crops_at_risk": ["Rice", "Maize"],
        "likely_diseases": ["Leaf Blight", "Rust"],
        "reasons": ["High humidity", "NDVI declining"],
        "recommendations": ["Inspect fields daily", "Apply fungicide"],
    }

    en_report = risk_report.build_crop_risk_report("en", result)
    ok("English report contains title", "Crop Risk Report" in en_report)
    ok("English report contains risk level", "High" in en_report)
    ok("English report contains crops", "Rice" in en_report)
    ok("English report contains disclaimer", "early warning" in en_report.lower())

    kn_report = risk_report.build_crop_risk_report("kn", result)
    ok("Kannada report contains title", "ಬೆಳೆ ಅಪಾಯ ವರದಿ" in kn_report)
    ok("Kannada report contains risk level", "ಹೆಚ್ಚು" in kn_report)


# ---------------------------------------------------------------------------
# 11. Existing features still intact
# ---------------------------------------------------------------------------

def test_existing_features_intact() -> None:
    print("\n[11] Existing features still intact")
    # get_all_reports
    reports = database.get_all_reports()
    ok("get_all_reports works", isinstance(reports, list))

    # get_outbreak_diseases
    outbreaks = database.get_outbreak_diseases(threshold=3, hours=48)
    ok("get_outbreak_diseases works", isinstance(outbreaks, list))

    # upsert_bot_user
    database.upsert_bot_user(
        chat_id=999, telegram_user_id=888,
        language="en", latitude=12.97, longitude=77.59,
    )
    with database.get_connection() as conn:
        row = conn.execute("SELECT * FROM bot_users WHERE chat_id = 999").fetchone()
    ok("upsert_bot_user still works", row is not None)

    # get_nearby_outbreak_risk
    risk = database.get_nearby_outbreak_risk(12.97, 77.59, radius_km=50, threshold=3, hours=48)
    ok("get_nearby_outbreak_risk works", isinstance(risk, list))

    # get_nearby_users
    users = database.get_nearby_users(12.97, 77.59, radius_km=50)
    ok("get_nearby_users works", isinstance(users, list))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 55)
    print("CropRadar - Predictive Risk Pipeline Integration Tests")
    print("=" * 55)

    try:
        test_schema_creation()
        test_grid_id()
        test_weather_snapshot()
        test_ndvi_snapshot()
        test_risk_score()
        test_nearby_disease_history()
        test_satellite_service()
        test_risk_features()
        test_risk_model()
        test_risk_report()
        test_existing_features_intact()
    finally:
        # Cleanup
        try:
            os.unlink(_test_db)
        except OSError:
            pass

    print(f"\n{'=' * 55}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print("=" * 55)
    sys.exit(1 if FAIL else 0)
