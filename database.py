"""
database.py - SQLite database layer for CropRadar
"""

import math
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = "cropradar.db"

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
    timestamp     TEXT    NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(CREATE_TABLE_SQL)
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
) -> int:
    timestamp = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO disease_reports
                (disease_type, confidence, remedy, prevention, latitude, longitude, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (disease_type, confidence, remedy, prevention, latitude, longitude, timestamp),
        )
        conn.commit()
        return cur.lastrowid


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
            (cutoff,),
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
