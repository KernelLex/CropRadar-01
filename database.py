"""
database.py - SQLite database layer for CropRadar
"""

import math
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Always resolve relative to THIS file so the DB is found regardless of CWD
DB_PATH = str(Path(__file__).resolve().parent / "cropradar.db")

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS disease_reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    disease_type  TEXT    NOT NULL,
    confidence    TEXT,
    remedy        TEXT,
    prevention    TEXT,
    latitude      REAL,
    longitude     REAL,
    photo_path    TEXT,
    timestamp     TEXT    NOT NULL
);
"""

CREATE_BOT_USERS_SQL = """
CREATE TABLE IF NOT EXISTS bot_users (
    chat_id           INTEGER PRIMARY KEY,
    telegram_user_id  INTEGER,
    language          TEXT    DEFAULT 'en',
    latitude          REAL,
    longitude         REAL,
    crop_type         TEXT,
    is_active         INTEGER DEFAULT 1,
    created_at        TEXT    NOT NULL,
    last_seen         TEXT    NOT NULL,
    registered_at     TEXT
);
"""

CREATE_WHATSAPP_USERS_SQL = """
CREATE TABLE IF NOT EXISTS whatsapp_users (
    wa_number   TEXT    PRIMARY KEY,
    language    TEXT    DEFAULT 'en',
    latitude    REAL,
    longitude   REAL,
    crop_type   TEXT,
    is_active   INTEGER DEFAULT 1,
    created_at  TEXT    NOT NULL,
    last_seen   TEXT    NOT NULL,
    registered_at TEXT
);
"""

CREATE_APP_DEVICES_SQL = """
CREATE TABLE IF NOT EXISTS app_devices (
    fcm_token   TEXT    PRIMARY KEY,
    language    TEXT    DEFAULT 'en',
    latitude    REAL,
    longitude   REAL,
    crop_type   TEXT,
    is_active   INTEGER DEFAULT 1,
    created_at  TEXT    NOT NULL,
    last_seen   TEXT    NOT NULL,
    registered_at TEXT
);
"""

CREATE_OUTBREAK_NOTIFICATIONS_SQL = """
CREATE TABLE IF NOT EXISTS outbreak_notifications (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    disease_type     TEXT    NOT NULL,
    center_latitude  REAL    NOT NULL,
    center_longitude REAL    NOT NULL,
    radius_km        REAL    DEFAULT 50,
    triggered_at     TEXT    NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Predictive risk tables
# ---------------------------------------------------------------------------

CREATE_WEATHER_SNAPSHOTS_SQL = """
CREATE TABLE IF NOT EXISTS weather_snapshots (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    grid_id           TEXT    NOT NULL,
    latitude          REAL    NOT NULL,
    longitude         REAL    NOT NULL,
    date              TEXT    NOT NULL,
    temperature_mean  REAL,
    humidity_mean     REAL,
    precipitation_sum REAL,
    wind_speed_mean   REAL,
    dew_point         REAL,
    cloud_cover       REAL,
    source            TEXT,
    created_at        TEXT    NOT NULL
);
"""

CREATE_NDVI_SNAPSHOTS_SQL = """
CREATE TABLE IF NOT EXISTS ndvi_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    grid_id         TEXT    NOT NULL,
    latitude        REAL    NOT NULL,
    longitude       REAL    NOT NULL,
    date            TEXT    NOT NULL,
    ndvi_mean       REAL,
    ndvi_change_7d  REAL,
    ndvi_change_14d REAL,
    source          TEXT,
    created_at      TEXT    NOT NULL
);
"""

CREATE_RISK_SCORES_SQL = """
CREATE TABLE IF NOT EXISTS risk_scores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    grid_id       TEXT    NOT NULL,
    latitude      REAL    NOT NULL,
    longitude     REAL    NOT NULL,
    disease_type  TEXT,
    crop_type     TEXT,
    date          TEXT    NOT NULL,
    risk_score    REAL,
    risk_level    TEXT,
    reason_json   TEXT,
    created_at    TEXT    NOT NULL
);
"""


CREATE_DAILY_ALERTS_LOG_SQL = """
CREATE TABLE IF NOT EXISTS daily_alerts_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_key    TEXT    NOT NULL,
    channel     TEXT    NOT NULL,
    alert_type  TEXT    NOT NULL,
    sent_at     TEXT    NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.execute(CREATE_BOT_USERS_SQL)
        conn.execute(CREATE_WHATSAPP_USERS_SQL)
        conn.execute(CREATE_APP_DEVICES_SQL)
        conn.execute(CREATE_OUTBREAK_NOTIFICATIONS_SQL)
        conn.execute(CREATE_WEATHER_SNAPSHOTS_SQL)
        conn.execute(CREATE_NDVI_SNAPSHOTS_SQL)
        conn.execute(CREATE_RISK_SCORES_SQL)
        conn.execute(CREATE_DAILY_ALERTS_LOG_SQL)
        # Migrations for existing databases
        for migration in [
            "ALTER TABLE disease_reports ADD COLUMN photo_path TEXT",
            "ALTER TABLE bot_users ADD COLUMN crop_type TEXT",
            "ALTER TABLE bot_users ADD COLUMN registered_at TEXT",
            "ALTER TABLE whatsapp_users ADD COLUMN crop_type TEXT",
            "ALTER TABLE whatsapp_users ADD COLUMN registered_at TEXT",
            "ALTER TABLE app_devices ADD COLUMN crop_type TEXT",
            "ALTER TABLE app_devices ADD COLUMN registered_at TEXT",
        ]:
            try:
                conn.execute(migration)
            except Exception:
                pass
        conn.commit()



# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def insert_report(
    disease_type: str,
    confidence: str,
    remedy: str,
    prevention: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    photo_path: Optional[str] = None,
) -> int:
    timestamp = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO disease_reports
                (disease_type, confidence, remedy, prevention,
                 latitude, longitude, photo_path, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (disease_type, confidence, remedy, prevention,
             latitude, longitude, photo_path, timestamp),
        )
        conn.commit()
        return cur.lastrowid


def update_report_photo(report_id: int, photo_path: str) -> None:
    """Store the persisted photo file path for a report."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE disease_reports SET photo_path = ? WHERE id = ?",
            (photo_path, report_id),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_all_reports() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM disease_reports ORDER BY timestamp DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_reports_by_disease(disease_type: str, hours: int = 48) -> list[dict]:
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM disease_reports
            WHERE disease_type = ? AND timestamp >= ?
            ORDER BY timestamp DESC
            """,
            (disease_type, cutoff),
        ).fetchall()
    return [dict(r) for r in rows]


def get_outbreak_diseases(threshold: int = 3, hours: int = 48) -> list[dict]:
    """Global outbreak: diseases with >= threshold reports in window."""
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT disease_type, COUNT(*) as count
            FROM disease_reports
            WHERE timestamp >= ?
            GROUP BY disease_type
            HAVING count >= ?
            ORDER BY count DESC
            """,
            (cutoff, threshold),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Geo-spatial helpers
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in kilometres between two points."""
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_nearby_outbreak_risk(
    lat: float,
    lon: float,
    radius_km: float = 50,
    threshold: int = 3,
    hours: int = 48,
) -> list[dict]:
    """
    Return diseases that have >= threshold reports within radius_km of (lat, lon)
    in the last hours window.
    Each entry: {disease_type, count}.
    """
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

    # Fetch candidate rows (with coordinates) inside the time window
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT disease_type, latitude, longitude
            FROM disease_reports
            WHERE timestamp >= ?
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            """,
            (cutoff,)
        ).fetchall()

    # Count per disease, filtered by distance
    counts: dict[str, int] = {}
    for row in rows:
        dist = _haversine_km(lat, lon, row["latitude"], row["longitude"])
        if dist <= radius_km:
            counts[row["disease_type"]] = counts.get(row["disease_type"], 0) + 1

    return [
        {"disease_type": disease, "count": count}
        for disease, count in sorted(counts.items(), key=lambda x: -x[1])
        if count >= threshold
    ]


# ---------------------------------------------------------------------------
# Bot-user persistence
# ---------------------------------------------------------------------------

def upsert_bot_user(
    chat_id: int,
    telegram_user_id: int,
    language: str,
    latitude: float,
    longitude: float,
    crop_type: Optional[str] = None,
) -> None:
    """Insert or update a Telegram bot user record."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO bot_users
                (chat_id, telegram_user_id, language, latitude, longitude,
                 crop_type, is_active, created_at, last_seen, registered_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                telegram_user_id = excluded.telegram_user_id,
                language         = excluded.language,
                latitude         = excluded.latitude,
                longitude        = excluded.longitude,
                crop_type        = COALESCE(excluded.crop_type, bot_users.crop_type),
                is_active        = 1,
                last_seen        = excluded.last_seen
            """,
            (chat_id, telegram_user_id, language, latitude, longitude,
             crop_type, now, now, now),
        )
        conn.commit()


def get_nearby_users(
    lat: float, lon: float, radius_km: float = 50
) -> list[dict]:
    """Return active bot users whose saved location is within radius_km."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT chat_id, telegram_user_id, language, latitude, longitude
            FROM bot_users
            WHERE is_active = 1
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            """
        ).fetchall()

    return [
        dict(r) for r in rows
        if _haversine_km(lat, lon, r["latitude"], r["longitude"]) <= radius_km
    ]


# ---------------------------------------------------------------------------
# Crop type helpers
# ---------------------------------------------------------------------------

def update_bot_user_crop(chat_id: int, crop_type: str) -> None:
    """Set or update the crop type for a Telegram user."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE bot_users SET crop_type = ? WHERE chat_id = ?",
            (crop_type, chat_id),
        )
        conn.commit()


def update_whatsapp_user_crop(wa_number: str, crop_type: str) -> None:
    """Set or update the crop type for a WhatsApp user."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE whatsapp_users SET crop_type = ? WHERE wa_number = ?",
            (crop_type, wa_number),
        )
        conn.commit()


def update_app_device_crop(fcm_token: str, crop_type: str) -> None:
    """Set or update the crop type for an app device."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE app_devices SET crop_type = ? WHERE fcm_token = ?",
            (crop_type, fcm_token),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Proactive-alert helpers
# ---------------------------------------------------------------------------

def get_all_active_bot_users() -> list[dict]:
    """Return all active Telegram users with a saved location."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT chat_id, telegram_user_id, language, latitude, longitude,
                   crop_type, registered_at
            FROM bot_users
            WHERE is_active = 1
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_active_whatsapp_users() -> list[dict]:
    """Return all active WhatsApp users with a saved location."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT wa_number, language, latitude, longitude,
                   crop_type, registered_at
            FROM whatsapp_users
            WHERE is_active = 1
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_active_app_devices() -> list[dict]:
    """Return all active FCM devices with a saved location."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT fcm_token, language, latitude, longitude,
                   crop_type, registered_at
            FROM app_devices
            WHERE is_active = 1
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            """
        ).fetchall()
    return [dict(r) for r in rows]


def was_alert_sent_today(user_key: str, alert_type: str) -> bool:
    """Check if a proactive alert was already sent to this user today."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM daily_alerts_log
            WHERE user_key = ? AND alert_type = ? AND sent_at >= ?
            LIMIT 1
            """,
            (str(user_key), alert_type, today),
        ).fetchone()
    return row is not None


def was_alert_sent_this_week(user_key: str, alert_type: str) -> bool:
    """Check if a proactive alert was already sent to this user this week."""
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM daily_alerts_log
            WHERE user_key = ? AND alert_type = ? AND sent_at >= ?
            LIMIT 1
            """,
            (str(user_key), alert_type, week_ago),
        ).fetchone()
    return row is not None


def record_alert_sent(user_key: str, channel: str, alert_type: str) -> None:
    """Log that a proactive alert was sent."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_alerts_log (user_key, channel, alert_type, sent_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(user_key), channel, alert_type, now),
        )
        conn.commit()


def get_alert_log(limit: int = 100) -> list[dict]:
    """Return recent proactive alert log entries."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_alerts_log ORDER BY sent_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]



# ---------------------------------------------------------------------------
# Outbreak notification dedup
# ---------------------------------------------------------------------------

def was_outbreak_notified_recently(
    disease_type: str,
    lat: float,
    lon: float,
    radius_km: float = 20,
    hours: int = 24,
) -> bool:
    """Check if a similar outbreak alert was already sent recently."""
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT center_latitude, center_longitude
            FROM outbreak_notifications
            WHERE disease_type = ? AND triggered_at >= ?
            """,
            (disease_type, cutoff),
        ).fetchall()

    for row in rows:
        if _haversine_km(lat, lon, row["center_latitude"], row["center_longitude"]) <= radius_km:
            return True
    return False


def record_outbreak_notification(
    disease_type: str,
    lat: float,
    lon: float,
    radius_km: float = 50,
) -> int:
    """Log a sent outbreak notification for dedup purposes."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO outbreak_notifications
                (disease_type, center_latitude, center_longitude, radius_km, triggered_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (disease_type, lat, lon, radius_km, now),
        )
        conn.commit()
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Predictive-risk helpers
# ---------------------------------------------------------------------------

def lat_lon_to_grid_id(lat: float, lon: float, precision: int = 2) -> str:
    """Map lat/lon to a simple grid cell identifier (rounded coordinates)."""
    return f"{round(lat, precision)}_{round(lon, precision)}"


def save_weather_snapshot(
    grid_id: str, lat: float, lon: float, data: dict,
) -> int:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO weather_snapshots
                (grid_id, latitude, longitude, date,
                 temperature_mean, humidity_mean, precipitation_sum,
                 wind_speed_mean, dew_point, cloud_cover, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                grid_id, lat, lon, now,
                data.get("temperature_mean"),
                data.get("humidity_mean"),
                data.get("precipitation_sum"),
                data.get("wind_speed_mean"),
                data.get("dew_point"),
                data.get("cloud_cover"),
                data.get("source", "openweathermap"),
                now,
            ),
        )
        conn.commit()
        return cur.lastrowid


def get_recent_weather_snapshot(
    grid_id: str, max_age_hours: int = 6,
) -> Optional[dict]:
    cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM weather_snapshots
            WHERE grid_id = ? AND created_at >= ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (grid_id, cutoff),
        ).fetchone()
    return dict(row) if row else None


def save_ndvi_snapshot(
    grid_id: str, lat: float, lon: float, data: dict,
) -> int:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO ndvi_snapshots
                (grid_id, latitude, longitude, date,
                 ndvi_mean, ndvi_change_7d, ndvi_change_14d, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                grid_id, lat, lon, now,
                data.get("ndvi_mean"),
                data.get("ndvi_change_7d"),
                data.get("ndvi_change_14d"),
                data.get("source", "synthetic"),
                now,
            ),
        )
        conn.commit()
        return cur.lastrowid


def get_recent_ndvi_snapshot(
    grid_id: str, max_age_hours: int = 24,
) -> Optional[dict]:
    cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM ndvi_snapshots
            WHERE grid_id = ? AND created_at >= ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (grid_id, cutoff),
        ).fetchone()
    return dict(row) if row else None


def save_risk_score(
    grid_id: str, lat: float, lon: float, risk_data: dict,
) -> int:
    import json as _json
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO risk_scores
                (grid_id, latitude, longitude, disease_type, crop_type,
                 date, risk_score, risk_level, reason_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                grid_id, lat, lon,
                risk_data.get("disease_type"),
                risk_data.get("crop_type"),
                now,
                risk_data.get("risk_score"),
                risk_data.get("risk_level"),
                _json.dumps(risk_data.get("reasons", []), ensure_ascii=False),
                now,
            ),
        )
        conn.commit()
        return cur.lastrowid


def get_recent_risk_score(
    grid_id: str, max_age_hours: int = 6,
) -> Optional[dict]:
    cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM risk_scores
            WHERE grid_id = ? AND created_at >= ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (grid_id, cutoff),
        ).fetchone()
    return dict(row) if row else None


def get_nearby_disease_history(
    lat: float,
    lon: float,
    radius_km: float = 50,
    hours: int = 168,
) -> list[dict]:
    """
    Return all disease reports within radius_km of (lat, lon)
    in the last `hours` window (default 7 days).
    Unlike outbreak detection, this uses a longer window and no threshold.
    """
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT disease_type, confidence, latitude, longitude, timestamp
            FROM disease_reports
            WHERE timestamp >= ?
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            """,
            (cutoff,),
        ).fetchall()

    results = []
    for row in rows:
        dist = _haversine_km(lat, lon, row["latitude"], row["longitude"])
        if dist <= radius_km:
            r = dict(row)
            r["distance_km"] = round(dist, 2)
            results.append(r)
    return results


# ---------------------------------------------------------------------------
# WhatsApp user persistence
# ---------------------------------------------------------------------------

def upsert_whatsapp_user(
    wa_number: str,
    language: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    crop_type: Optional[str] = None,
) -> None:
    """Insert or update a WhatsApp bot user record."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO whatsapp_users
                (wa_number, language, latitude, longitude, crop_type,
                 is_active, created_at, last_seen, registered_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(wa_number) DO UPDATE SET
                language   = excluded.language,
                latitude   = COALESCE(excluded.latitude,  whatsapp_users.latitude),
                longitude  = COALESCE(excluded.longitude, whatsapp_users.longitude),
                crop_type  = COALESCE(excluded.crop_type, whatsapp_users.crop_type),
                is_active  = 1,
                last_seen  = excluded.last_seen
            """,
            (wa_number, language, latitude, longitude, crop_type, now, now, now),
        )
        conn.commit()


def get_nearby_whatsapp_users(
    lat: float, lon: float, radius_km: float = 50
) -> list[dict]:
    """Return active WhatsApp users whose saved location is within radius_km."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT wa_number, language, latitude, longitude
            FROM whatsapp_users
            WHERE is_active = 1
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            """
        ).fetchall()
    return [
        dict(r) for r in rows
        if _haversine_km(lat, lon, r["latitude"], r["longitude"]) <= radius_km
    ]


# ---------------------------------------------------------------------------
# Flutter app device (FCM) persistence
# ---------------------------------------------------------------------------

def upsert_app_device(
    fcm_token: str,
    language: str = "en",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    crop_type: Optional[str] = None,
) -> None:
    """Insert or update a Flutter app FCM device token."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO app_devices
                (fcm_token, language, latitude, longitude, crop_type,
                 is_active, created_at, last_seen, registered_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(fcm_token) DO UPDATE SET
                language   = excluded.language,
                latitude   = COALESCE(excluded.latitude,  app_devices.latitude),
                longitude  = COALESCE(excluded.longitude, app_devices.longitude),
                crop_type  = COALESCE(excluded.crop_type, app_devices.crop_type),
                is_active  = 1,
                last_seen  = excluded.last_seen
            """,
            (fcm_token, language, latitude, longitude, crop_type, now, now, now),
        )
        conn.commit()


def get_nearby_app_devices(
    lat: float, lon: float, radius_km: float = 50
) -> list[dict]:
    """Return active FCM tokens whose saved location is within radius_km."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT fcm_token, language, latitude, longitude
            FROM app_devices
            WHERE is_active = 1
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            """
        ).fetchall()
    return [
        dict(r) for r in rows
        if _haversine_km(lat, lon, r["latitude"], r["longitude"]) <= radius_km
    ]
