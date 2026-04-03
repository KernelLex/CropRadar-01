"""
api.py - FastAPI backend for CropRadar

Endpoints:
  POST /analyze-image  – diagnose a crop image
  POST /report         – store a disease report
  GET  /alerts         – check for outbreak conditions
"""

import os
import logging
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import database
import notifier
import vision_diagnosis

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CropRadar API",
    description="AI-powered crop disease detection and outbreak alerting.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure the DB and schema exist at startup
database.init_db()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DiagnosisResponse(BaseModel):
    disease_name: str
    confidence: str
    remedy: str
    prevention: str
    outbreak_alert: Optional[str] = None
    report_id: Optional[int] = None


class ReportRequest(BaseModel):
    disease_type: str
    confidence: str
    remedy: str
    prevention: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ReportResponse(BaseModel):
    report_id: int
    message: str


class AlertsResponse(BaseModel):
    outbreaks: list[dict]
    alert_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Outbreak helper
# ---------------------------------------------------------------------------

OUTBREAK_THRESHOLD = 3   # reports
OUTBREAK_WINDOW_HRS = 48  # hours

OUTBREAK_TEMPLATE = (
    "⚠️ Possible outbreak detected nearby. "
    "Farmers should monitor crops and apply preventive treatment."
)


def _check_outbreak(disease_name: str) -> Optional[str]:
    recent = database.get_recent_reports_by_disease(
        disease_name, hours=OUTBREAK_WINDOW_HRS
    )
    if len(recent) >= OUTBREAK_THRESHOLD:
        return OUTBREAK_TEMPLATE
    return None


logger = logging.getLogger(__name__)


def _maybe_broadcast_outbreak(
    disease_type: str,
    lat: Optional[float],
    lon: Optional[float],
) -> None:
    """Check outbreak threshold and send proactive alerts if warranted."""
    if lat is None or lon is None:
        return

    # Check localised outbreak around the new report's coordinates
    outbreaks = database.get_nearby_outbreak_risk(
        lat, lon,
        radius_km=50,
        threshold=OUTBREAK_THRESHOLD,
        hours=OUTBREAK_WINDOW_HRS,
    )

    # Find the entry for this specific disease
    match = next((o for o in outbreaks if o["disease_type"] == disease_type), None)
    if match is None:
        return

    # Dedup: skip if a similar alert was sent recently
    if database.was_outbreak_notified_recently(disease_type, lat, lon):
        logger.info(
            "Outbreak broadcast skipped (already notified): %s @ (%.4f, %.4f)",
            disease_type, lat, lon,
        )
        return

    # Find eligible users and send alerts
    users = database.get_nearby_users(lat, lon, radius_km=50)
    if not users:
        logger.info("Outbreak detected but no nearby users to notify.")
        return

    database.record_outbreak_notification(disease_type, lat, lon)
    notifier.broadcast_outbreak_alert(disease_type, match["count"], users)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "service": "CropRadar API"}


@app.post("/analyze-image", response_model=DiagnosisResponse, tags=["diagnosis"])
async def analyze_image(
    file: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    language: str = Form("en"),
):
    """
    Accept a crop image, run Vision AI diagnosis, persist the report,
    and return the structured result (with outbreak alert if applicable).
    """
    # ---- Save uploaded file to a temp path --------------------------------
    # On Windows, NamedTemporaryFile cannot be opened by a second process
    # (PIL/Gemini) while still held open. Close it first, then pass the path.
    suffix = Path(file.filename or "image.jpg").suffix or ".jpg"
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(tmp_fd, "wb") as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
        # File is now closed — safe to open from vision_diagnosis / PIL
        try:
            # ---- Run Vision AI --------------------------------------------
            result = vision_diagnosis.analyze_crop_image(tmp_path, language=language)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Vision AI error: {exc}") from exc
    finally:
        try:
            os.unlink(tmp_path)  # always clean up
        except OSError:
            pass

    disease_name = result.get("disease_name", "Unknown")
    confidence   = result.get("confidence", "Unknown")
    remedy       = result.get("remedy", "")
    prevention   = result.get("prevention", "")

    # ---- Persist report ---------------------------------------------------
    report_id = database.insert_report(
        disease_type=disease_name,
        confidence=confidence,
        remedy=remedy,
        prevention=prevention,
        latitude=latitude,
        longitude=longitude,
    )

    # ---- Outbreak check ---------------------------------------------------
    outbreak_alert = _check_outbreak(disease_name)

    # ---- Proactive broadcast (background) ---------------------------------
    threading.Thread(
        target=_maybe_broadcast_outbreak,
        args=(disease_name, latitude, longitude),
        daemon=True,
    ).start()

    return DiagnosisResponse(
        disease_name=disease_name,
        confidence=confidence,
        remedy=remedy,
        prevention=prevention,
        outbreak_alert=outbreak_alert,
        report_id=report_id,
    )


@app.post("/report", response_model=ReportResponse, tags=["reports"])
def add_report(body: ReportRequest):
    """
    Manually store a disease report (useful for testing or external integrations).
    """
    report_id = database.insert_report(
        disease_type=body.disease_type,
        confidence=body.confidence,
        remedy=body.remedy,
        prevention=body.prevention,
        latitude=body.latitude,
        longitude=body.longitude,
    )

    # Proactive broadcast (background)
    threading.Thread(
        target=_maybe_broadcast_outbreak,
        args=(body.disease_type, body.latitude, body.longitude),
        daemon=True,
    ).start()

    return ReportResponse(report_id=report_id, message="Report stored successfully.")


@app.get("/alerts", response_model=AlertsResponse, tags=["alerts"])
def get_alerts():
    """
    Return disease types with outbreak-level report counts
    (>= 3 within the last 48 hours).
    """
    outbreaks = database.get_outbreak_diseases(
        threshold=OUTBREAK_THRESHOLD,
        hours=OUTBREAK_WINDOW_HRS,
    )
    alert_message = OUTBREAK_TEMPLATE if outbreaks else None
    return AlertsResponse(outbreaks=outbreaks, alert_message=alert_message)


@app.get("/reports", tags=["reports"])
def list_reports():
    """Return all disease reports (used by the map dashboard)."""
    return database.get_all_reports()


class NearbyAlertsResponse(BaseModel):
    outbreaks: list[dict]
    alert_message: Optional[str] = None


@app.get("/nearby-alerts", response_model=NearbyAlertsResponse, tags=["alerts"])
def get_nearby_alerts(
    lat: float,
    lon: float,
    radius_km: float = 50,
):
    """
    Return diseases with >= 3 reports within radius_km of (lat, lon)
    in the last 48 hours. Used by the bot to pre-warn farmers.
    """
    outbreaks = database.get_nearby_outbreak_risk(
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        threshold=OUTBREAK_THRESHOLD,
        hours=OUTBREAK_WINDOW_HRS,
    )
    alert_message = OUTBREAK_TEMPLATE if outbreaks else None
    return NearbyAlertsResponse(outbreaks=outbreaks, alert_message=alert_message)

