"""
test_outbreak_broadcast.py - Lightweight integration tests for the
proactive outbreak broadcast feature.

Run:  python test_outbreak_broadcast.py
Uses a temporary SQLite database so the production DB is not affected.
"""

import os
import sys
import tempfile

# Use a temporary database for tests
_test_db = tempfile.mktemp(suffix=".db")
os.environ.setdefault("CROPRADAR_DB_PATH", _test_db)

import database  # noqa: E402  (must import after setting DB_PATH override)

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


def test_schema_creation() -> None:
    print("\n[1] Schema creation")
    database.init_db()
    with database.get_connection() as conn:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
    ok("disease_reports table exists", "disease_reports" in tables)
    ok("bot_users table exists", "bot_users" in tables)
    ok("outbreak_notifications table exists", "outbreak_notifications" in tables)


def test_upsert_bot_user() -> None:
    print("\n[2] Bot user upsert")
    database.upsert_bot_user(
        chat_id=100, telegram_user_id=200,
        language="en", latitude=12.97, longitude=77.59,
    )
    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM bot_users WHERE chat_id = 100"
        ).fetchone()
    ok("user inserted", row is not None)
    ok("language is en", row["language"] == "en")

    # Update same user
    database.upsert_bot_user(
        chat_id=100, telegram_user_id=200,
        language="kn", latitude=12.98, longitude=77.60,
    )
    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM bot_users WHERE chat_id = 100"
        ).fetchone()
    ok("language updated to kn", row["language"] == "kn")
    ok("latitude updated", abs(row["latitude"] - 12.98) < 0.001)


def test_get_nearby_users() -> None:
    print("\n[3] Nearby users lookup")
    # Add a second user far away
    database.upsert_bot_user(
        chat_id=101, telegram_user_id=201,
        language="en", latitude=28.61, longitude=77.23,  # Delhi (~1700 km away)
    )
    nearby = database.get_nearby_users(12.97, 77.59, radius_km=50)
    ok("only nearby user returned", len(nearby) == 1, f"got {len(nearby)}")
    ok("correct chat_id", nearby[0]["chat_id"] == 100)


def test_outbreak_flow() -> None:
    print("\n[4] Outbreak detection + notification dedup")
    disease = "Leaf Blight"
    lat, lon = 12.97, 77.59

    # Insert 3 reports at same coords
    for i in range(3):
        database.insert_report(
            disease_type=disease, confidence="High",
            remedy="Apply fungicide", prevention="Crop rotation",
            latitude=lat + i * 0.001, longitude=lon + i * 0.001,
        )

    # Check outbreak risk
    outbreaks = database.get_nearby_outbreak_risk(lat, lon, radius_km=50, threshold=3, hours=48)
    found = any(o["disease_type"] == disease for o in outbreaks)
    ok("outbreak detected for disease", found)

    # Not yet notified
    ok("not notified yet", not database.was_outbreak_notified_recently(disease, lat, lon))

    # Record notification
    database.record_outbreak_notification(disease, lat, lon)

    # Now it should be notified recently
    ok("marked as notified", database.was_outbreak_notified_recently(disease, lat, lon))

    # Nearby coordinates should also count as duplicate
    ok(
        "nearby coords also deduped",
        database.was_outbreak_notified_recently(disease, lat + 0.01, lon + 0.01),
    )

    # Far away same disease should NOT be deduped
    ok(
        "far coords not deduped",
        not database.was_outbreak_notified_recently(disease, 28.61, 77.23),
    )


def test_existing_features_intact() -> None:
    print("\n[5] Existing features intact")
    # get_all_reports still works
    reports = database.get_all_reports()
    ok("get_all_reports returns data", len(reports) >= 3)

    # get_outbreak_diseases still works
    outbreaks = database.get_outbreak_diseases(threshold=3, hours=48)
    ok("get_outbreak_diseases works", isinstance(outbreaks, list))

    # get_recent_reports_by_disease still works
    recent = database.get_recent_reports_by_disease("Leaf Blight", hours=48)
    ok("get_recent_reports_by_disease works", len(recent) >= 3)


if __name__ == "__main__":
    print("=" * 50)
    print("CropRadar - Outbreak Broadcast Integration Tests")
    print("=" * 50)

    try:
        test_schema_creation()
        test_upsert_bot_user()
        test_get_nearby_users()
        test_outbreak_flow()
        test_existing_features_intact()
    finally:
        # Cleanup
        try:
            os.unlink(_test_db)
        except OSError:
            pass

    print(f"\n{'=' * 50}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print("=" * 50)
    sys.exit(1 if FAIL else 0)
