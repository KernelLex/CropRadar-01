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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database
import notifier
import vision_diagnosis
import audio_transcription
import scheduler as scheduler_module
import crop_stage

# Directory where uploaded crop photos are persisted
PHOTOS_DIR = Path("photos")
PHOTOS_DIR.mkdir(exist_ok=True)


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

# Serve persisted crop photos as static files: GET /photos/{filename}
app.mount("/photos", StaticFiles(directory=str(PHOTOS_DIR)), name="photos")


@app.on_event("startup")
def startup_event():
    """Start the proactive alert scheduler when FastAPI boots."""
    scheduler_module.start_scheduler()


@app.on_event("shutdown")
def shutdown_event():
    """Stop the scheduler gracefully."""
    scheduler_module.stop_scheduler()


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
    photo_url: Optional[str] = None


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


class TranscriptionResponse(BaseModel):
    text: str


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

    # Gather users across all three channels
    telegram_users  = database.get_nearby_users(lat, lon, radius_km=50)
    whatsapp_users  = database.get_nearby_whatsapp_users(lat, lon, radius_km=50)
    app_devices     = database.get_nearby_app_devices(lat, lon, radius_km=50)

    if not telegram_users and not whatsapp_users and not app_devices:
        logger.info("Outbreak detected but no nearby users to notify.")
        return

    database.record_outbreak_notification(disease_type, lat, lon)
    notifier.broadcast_outbreak_alert(
        disease_type, match["count"],
        telegram_users, whatsapp_users, app_devices,
    )


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

        disease_name = result.get("disease_name", "Unknown")
        confidence   = result.get("confidence", "Unknown")
        remedy       = result.get("remedy", "")
        prevention   = result.get("prevention", "")

        # ---- Persist report -----------------------------------------------
        report_id = database.insert_report(
            disease_type=disease_name,
            confidence=confidence,
            remedy=remedy,
            prevention=prevention,
            latitude=latitude,
            longitude=longitude,
        )

        # ---- Save photo permanently ---------------------------------------
        photo_filename = f"{report_id}.jpg"
        photo_path = PHOTOS_DIR / photo_filename
        shutil.copy2(tmp_path, photo_path)
        database.update_report_photo(report_id, str(photo_path))

    finally:
        try:
            os.unlink(tmp_path)  # always clean up temp
        except OSError:
            pass

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
        photo_url=f"/photos/{photo_filename}",
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


class DeviceRegistrationRequest(BaseModel):
    fcm_token: str
    language: str = "en"
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@app.post("/register-device", tags=["notifications"])
def register_device(body: DeviceRegistrationRequest):
    """
    Register or update a Flutter app FCM token so it receives
    proactive outbreak push notifications.
    """
    database.upsert_app_device(
        fcm_token=body.fcm_token,
        language=body.language,
        latitude=body.latitude,
        longitude=body.longitude,
    )
    return {"status": "registered"}


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


@app.post("/transcribe-audio", response_model=TranscriptionResponse, tags=["audio"])
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form("en"),
):
    """
    Accept an audio file (OGG/MP3), run Audio AI transcription and return text.
    """
    suffix = Path(file.filename or "audio.ogg").suffix or ".ogg"
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(tmp_fd, "wb") as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)

        try:
            text = audio_transcription.transcribe_audio_file(tmp_path, language=language)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Audio AI error: {exc}") from exc

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return TranscriptionResponse(text=text)


# ---------------------------------------------------------------------------
# Predictive risk routes
# ---------------------------------------------------------------------------

import risk_features
import risk_model
import risk_report as risk_report_module


class RiskAnalysisResponse(BaseModel):
    risk_score: float
    risk_level: str
    likely_crops_at_risk: list[str]
    likely_diseases: list[str]
    reasons: list[str]
    recommendations: list[str]
    score_breakdown: dict


@app.get("/risk-nearby", response_model=RiskAnalysisResponse, tags=["risk"])
def get_risk_nearby(lat: float, lon: float):
    """
    Run predictive risk analysis for a given location.
    Returns structured risk assessment (for testing/dashboard).
    """
    features = risk_features.build_risk_features(lat, lon)
    result = risk_model.score_area_risk(features)
    return RiskAnalysisResponse(
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        likely_crops_at_risk=result["likely_crops_at_risk"],
        likely_diseases=result["likely_diseases"],
        reasons=result["reasons"],
        recommendations=result["recommendations"],
        score_breakdown=result["score_breakdown"],
    )


@app.get("/risk-report", tags=["risk"])
def get_risk_report(lat: float, lon: float, language: str = "en"):
    """
    Run predictive risk analysis and return formatted text (used by bots).
    """
    features = risk_features.build_risk_features(lat, lon)
    result = risk_model.score_area_risk(features)
    report_text = risk_report_module.build_crop_risk_report(language, result)
    return {
        "risk_level": result["risk_level"],
        "risk_score": result["risk_score"],
        "report_text": report_text,
    }


# ---------------------------------------------------------------------------
# Scheduler & proactive intelligence routes
# ---------------------------------------------------------------------------

@app.get("/scheduler/status", tags=["scheduler"])
def scheduler_status():
    """Check scheduler health: running state, jobs, last run times."""
    return scheduler_module.get_scheduler_status()


@app.post("/scheduler/trigger-daily", tags=["scheduler"])
def trigger_daily():
    """Manually trigger the daily risk alert job (admin/testing)."""
    import threading
    threading.Thread(target=scheduler_module.trigger_daily_job, daemon=True).start()
    return {"status": "triggered", "job": "daily_risk"}


@app.post("/scheduler/trigger-weekly", tags=["scheduler"])
def trigger_weekly():
    """Manually trigger the weekly stage intelligence job (admin/testing)."""
    import threading
    threading.Thread(target=scheduler_module.trigger_weekly_job, daemon=True).start()
    return {"status": "triggered", "job": "weekly_stage"}


@app.post("/scheduler/trigger-outbreak-scan", tags=["scheduler"])
def trigger_outbreak():
    """Manually trigger the outbreak cluster scan."""
    import threading
    threading.Thread(target=scheduler_module.trigger_outbreak_scan, daemon=True).start()
    return {"status": "triggered", "job": "outbreak_scan"}


@app.get("/crop-stage", tags=["intelligence"])
def get_crop_stage(crop_type: str, registered_at: str):
    """Estimate current crop growth stage from crop type + registration date."""
    info = crop_stage.estimate_growth_stage(crop_type, registered_at)
    if not info:
        raise HTTPException(status_code=400, detail="Cannot estimate stage.")
    return info


@app.get("/crop-stage-report", tags=["intelligence"])
def get_crop_stage_report(
    crop_type: str, registered_at: str, language: str = "en",
):
    """Get formatted crop stage advisory text."""
    info = crop_stage.estimate_growth_stage(crop_type, registered_at)
    if not info:
        raise HTTPException(status_code=400, detail="Cannot estimate stage.")
    report = crop_stage.build_stage_report(language, info)
    return {"stage_info": info, "report_text": report}


@app.get("/alerts-log", tags=["scheduler"])
def get_alerts_log(limit: int = 100):
    """Return recent proactive alert log entries."""
    return database.get_alert_log(limit=limit)


@app.get("/supported-crops", tags=["intelligence"])
def get_supported_crops():
    """Return the list of supported crop types."""
    return {"crops": crop_stage.SUPPORTED_CROPS}
