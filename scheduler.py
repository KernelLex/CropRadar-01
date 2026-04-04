"""
scheduler.py - Proactive alert scheduler for CropRadar.

Runs background jobs inside the FastAPI process using APScheduler:
  1. Daily job  (7:00 AM IST) — weather risk + NDVI alerts for all users
  2. Weekly job (Monday 8:00 AM IST) — crop stage intelligence
  3. Outbreak scan (every 1 minute) — cluster detection + broadcast

All alerts are sent via notifier.py across Telegram, WhatsApp, and FCM.
Deduplication via daily_alerts_log table prevents spam.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import database
import notifier
import weather_service
import satellite_service
import risk_model
import risk_report as risk_report_module
import crop_stage

logger = logging.getLogger(__name__)

# Timezone for scheduling
TZ = "Asia/Kolkata"

# Global scheduler instance
_scheduler: BackgroundScheduler | None = None

# Track last run times for the status endpoint
_last_run = {
    "daily_risk": None,
    "weekly_stage": None,
    "outbreak_scan": None,
}


# ---------------------------------------------------------------------------
# Daily risk job
# ---------------------------------------------------------------------------

def _run_daily_risk_job():
    """
    For every registered user (all channels), fetch weather & NDVI,
    calculate risk, and send alerts if risk >= Medium.
    """
    logger.info("=== Daily risk job started ===")
    _last_run["daily_risk"] = datetime.utcnow().isoformat()

    tg_sent = wa_sent = fcm_sent = 0

    # ── Telegram users ────────────────────────────────────────────────────
    try:
        tg_users = database.get_all_active_bot_users()
    except Exception as exc:
        logger.error("Failed to get TG users: %s", exc)
        tg_users = []

    for user in tg_users:
        key = str(user["chat_id"])
        if database.was_alert_sent_today(key, "daily_risk"):
            continue
        try:
            msg = _build_daily_message(
                user["latitude"], user["longitude"],
                user.get("language", "en"),
                user.get("crop_type"),
            )
            if msg:
                ok = notifier.send_proactive_telegram(user["chat_id"], msg)
                if ok:
                    database.record_alert_sent(key, "telegram", "daily_risk")
                    tg_sent += 1
        except Exception as exc:
            logger.warning("Daily risk TG error for %s: %s", key, exc)

    # ── WhatsApp users ─────────────────────────────────────────────────────
    try:
        wa_users = database.get_all_active_whatsapp_users()
    except Exception as exc:
        logger.error("Failed to get WA users: %s", exc)
        wa_users = []

    for user in wa_users:
        key = user["wa_number"]
        if database.was_alert_sent_today(key, "daily_risk"):
            continue
        try:
            msg = _build_daily_message(
                user["latitude"], user["longitude"],
                user.get("language", "en"),
                user.get("crop_type"),
            )
            if msg:
                ok = notifier.send_proactive_whatsapp(key, msg)
                if ok:
                    database.record_alert_sent(key, "whatsapp", "daily_risk")
                    wa_sent += 1
        except Exception as exc:
            logger.warning("Daily risk WA error for %s: %s", key, exc)

    # ── FCM devices ────────────────────────────────────────────────────────
    try:
        app_devices = database.get_all_active_app_devices()
    except Exception as exc:
        logger.error("Failed to get FCM devices: %s", exc)
        app_devices = []

    for device in app_devices:
        key = device["fcm_token"]
        if database.was_alert_sent_today(key, "daily_risk"):
            continue
        try:
            result = _compute_risk(
                device["latitude"], device["longitude"],
                device.get("crop_type"),
            )
            if result and result["risk_level"] in ("Medium", "High"):
                title = f"⚠️ {result['risk_level']} crop risk today"
                body = "; ".join(result.get("reasons", [])[:2])
                ok = notifier.send_proactive_fcm(
                    key, title, body,
                    data={"type": "daily_risk", "risk_level": result["risk_level"]},
                )
                if ok:
                    database.record_alert_sent(key, "fcm", "daily_risk")
                    fcm_sent += 1
        except Exception as exc:
            logger.warning("Daily risk FCM error: %s", exc)

    logger.info(
        "=== Daily risk job done — TG=%d WA=%d FCM=%d ===",
        tg_sent, wa_sent, fcm_sent,
    )


def _build_daily_message(lat, lon, language, crop_type=None):
    """Build a daily risk digest for messaging channels (TG / WA)."""
    result = _compute_risk(lat, lon, crop_type)
    if not result:
        return None

    # Only send if risk is Medium or High
    if result["risk_level"] == "Low":
        return None

    # Build the formatted report
    report = risk_report_module.build_crop_risk_report(language, result)

    # Add NDVI drop warning if applicable
    ndvi_msg = _check_ndvi_drop(lat, lon, language)
    if ndvi_msg:
        report += "\n\n" + ndvi_msg

    return report


def _compute_risk(lat, lon, crop_type=None):
    """Run the risk pipeline for a location."""
    try:
        import risk_features
        features = risk_features.build_risk_features(lat, lon)
        return risk_model.score_area_risk(features)
    except Exception as exc:
        logger.warning("Risk computation failed for (%.4f, %.4f): %s", lat, lon, exc)
        return None


def _check_ndvi_drop(lat, lon, language):
    """Check for vegetation health decline and return alert text if found."""
    try:
        ndvi = satellite_service.get_ndvi_features(lat, lon)
        if not ndvi:
            return None
        change = ndvi.get("ndvi_change_7d")
        if change is not None and change < -0.05:
            if language == "kn":
                return (
                    "📉 *ಸಸ್ಯ ಆರೋಗ್ಯ ಎಚ್ಚರಿಕೆ*\n"
                    "ನಿಮ್ಮ ಪ್ರದೇಶದಲ್ಲಿ ಬೆಳೆ ಆರೋಗ್ಯ ಕುಸಿಯುತ್ತಿದೆ.\n"
                    "ಹೊಲಗಳನ್ನು ತಕ್ಷಣ ಪರಿಶೀಲಿಸಿ."
                )
            return (
                "📉 *Vegetation Health Alert*\n"
                "Crop health is declining in your region.\n"
                "Check your fields immediately."
            )
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Weekly crop stage job
# ---------------------------------------------------------------------------

def _run_weekly_stage_job():
    """
    For every user with a crop_type set, estimate the growth stage
    and send a weekly advisory.
    """
    logger.info("=== Weekly stage job started ===")
    _last_run["weekly_stage"] = datetime.utcnow().isoformat()

    tg_sent = wa_sent = fcm_sent = 0

    # ── Telegram users ────────────────────────────────────────────────────
    try:
        tg_users = database.get_all_active_bot_users()
    except Exception:
        tg_users = []

    for user in tg_users:
        key = str(user["chat_id"])
        ct = user.get("crop_type")
        reg = user.get("registered_at")
        if not ct or not reg:
            continue
        if database.was_alert_sent_this_week(key, "weekly_stage"):
            continue
        try:
            stage_info = crop_stage.estimate_growth_stage(ct, reg)
            if not stage_info:
                continue
            msg = crop_stage.build_stage_report(
                user.get("language", "en"), stage_info,
            )
            ok = notifier.send_proactive_telegram(user["chat_id"], msg)
            if ok:
                database.record_alert_sent(key, "telegram", "weekly_stage")
                tg_sent += 1
        except Exception as exc:
            logger.warning("Weekly stage TG error for %s: %s", key, exc)

    # ── WhatsApp users ─────────────────────────────────────────────────────
    try:
        wa_users = database.get_all_active_whatsapp_users()
    except Exception:
        wa_users = []

    for user in wa_users:
        key = user["wa_number"]
        ct = user.get("crop_type")
        reg = user.get("registered_at")
        if not ct or not reg:
            continue
        if database.was_alert_sent_this_week(key, "weekly_stage"):
            continue
        try:
            stage_info = crop_stage.estimate_growth_stage(ct, reg)
            if not stage_info:
                continue
            msg = crop_stage.build_stage_report(
                user.get("language", "en"), stage_info,
            )
            ok = notifier.send_proactive_whatsapp(key, msg)
            if ok:
                database.record_alert_sent(key, "whatsapp", "weekly_stage")
                wa_sent += 1
        except Exception as exc:
            logger.warning("Weekly stage WA error for %s: %s", key, exc)

    # ── FCM devices ────────────────────────────────────────────────────────
    try:
        app_devices = database.get_all_active_app_devices()
    except Exception:
        app_devices = []

    for device in app_devices:
        key = device["fcm_token"]
        ct = device.get("crop_type")
        reg = device.get("registered_at")
        if not ct or not reg:
            continue
        if database.was_alert_sent_this_week(key, "weekly_stage"):
            continue
        try:
            stage_info = crop_stage.estimate_growth_stage(ct, reg)
            if not stage_info:
                continue
            title = f"🌱 {ct} — {stage_info['stage_name']} stage"
            risks = crop_stage.get_stage_specific_risks(ct, stage_info["stage_name"])
            body = risks[0] if risks else "Check your crop stage advisory."
            ok = notifier.send_proactive_fcm(
                key, title, body,
                data={"type": "weekly_stage", "crop": ct},
            )
            if ok:
                database.record_alert_sent(key, "fcm", "weekly_stage")
                fcm_sent += 1
        except Exception as exc:
            logger.warning("Weekly stage FCM error: %s", exc)

    logger.info(
        "=== Weekly stage job done — TG=%d WA=%d FCM=%d ===",
        tg_sent, wa_sent, fcm_sent,
    )


# ---------------------------------------------------------------------------
# Outbreak scan job
# ---------------------------------------------------------------------------

def _run_outbreak_scan_job():
    """
    Periodically scan recent disease reports for cluster patterns.
    If 3+ same disease within 50km and not recently notified, broadcast.
    """
    logger.info("=== Outbreak scan job started ===")
    _last_run["outbreak_scan"] = datetime.utcnow().isoformat()

    try:
        # Get all recent reports with location
        reports = database.get_all_reports()
    except Exception as exc:
        logger.error("Outbreak scan failed to get reports: %s", exc)
        return

    # Filter to reports with location in last 48h
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(hours=48)).isoformat()
    recent = [
        r for r in reports
        if r.get("latitude") and r.get("longitude")
        and r.get("timestamp", "") >= cutoff
    ]

    if not recent:
        logger.info("No recent geo-tagged reports — skipping outbreak scan.")
        return

    # Group by disease type and check clusters
    from collections import defaultdict
    by_disease = defaultdict(list)
    for r in recent:
        by_disease[r["disease_type"]].append(r)

    alerts_sent = 0
    for disease, reps in by_disease.items():
        if len(reps) < 3:
            continue

        # Use centroid of reports as the cluster center
        avg_lat = sum(r["latitude"] for r in reps) / len(reps)
        avg_lon = sum(r["longitude"] for r in reps) / len(reps)

        # Check if nearby cluster already notified
        if database.was_outbreak_notified_recently(disease, avg_lat, avg_lon):
            continue

        # Find nearby users across all channels
        tg_users = database.get_nearby_users(avg_lat, avg_lon, radius_km=50)
        wa_users = database.get_nearby_whatsapp_users(avg_lat, avg_lon, radius_km=50)
        app_devs = database.get_nearby_app_devices(avg_lat, avg_lon, radius_km=50)

        if not tg_users and not wa_users and not app_devs:
            continue

        database.record_outbreak_notification(disease, avg_lat, avg_lon)
        notifier.broadcast_outbreak_alert(
            disease, len(reps),
            tg_users, wa_users, app_devs,
        )
        alerts_sent += 1

    logger.info("=== Outbreak scan done — %d alerts sent ===", alerts_sent)


# ---------------------------------------------------------------------------
# Scheduler control
# ---------------------------------------------------------------------------

def start_scheduler():
    """Start the background scheduler with all jobs. Call once at app startup."""
    global _scheduler

    if _scheduler and _scheduler.running:
        logger.warning("Scheduler already running — skipping start.")
        return

    _scheduler = BackgroundScheduler(timezone=TZ)

    # Daily risk alerts — every day at 7:00 AM IST
    _scheduler.add_job(
        _run_daily_risk_job,
        CronTrigger(hour=7, minute=0, timezone=TZ),
        id="daily_risk",
        name="Daily Risk Alerts",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Weekly crop stage — every Monday at 8:00 AM IST
    _scheduler.add_job(
        _run_weekly_stage_job,
        CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=TZ),
        id="weekly_stage",
        name="Weekly Crop Stage Intelligence",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Outbreak scan — every 1 minute
    _scheduler.add_job(
        _run_outbreak_scan_job,
        CronTrigger(minute="*/1", timezone=TZ),
        id="outbreak_scan",
        name="Outbreak Cluster Scan",
        replace_existing=True,
        misfire_grace_time=60,
    )

    _scheduler.start()
    logger.info(
        "✅ CropRadar scheduler started — "
        "daily@07:00 IST, weekly@Mon 08:00 IST, outbreak@every 1min"
    )


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
        _scheduler = None


def get_scheduler_status() -> dict:
    """Return current scheduler status for monitoring."""
    if not _scheduler:
        return {"running": False, "jobs": [], "last_run": _last_run}

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })

    return {
        "running": _scheduler.running,
        "jobs": jobs,
        "last_run": _last_run,
    }


def trigger_daily_job():
    """Manually trigger the daily risk job (e.g. for admin testing)."""
    logger.info("Manual trigger: daily risk job")
    _run_daily_risk_job()


def trigger_weekly_job():
    """Manually trigger the weekly stage job (e.g. for admin testing)."""
    logger.info("Manual trigger: weekly stage job")
    _run_weekly_stage_job()


def trigger_outbreak_scan():
    """Manually trigger outbreak scan."""
    logger.info("Manual trigger: outbreak scan")
    _run_outbreak_scan_job()
