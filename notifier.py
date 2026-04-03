"""
notifier.py - Proactive Telegram outbreak broadcast for CropRadar

Sends bilingual alert messages to eligible bot users using the
Telegram Bot API directly (via requests).
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# ---------------------------------------------------------------------------
# Bilingual alert templates
# ---------------------------------------------------------------------------

ALERT_TEMPLATES = {
    "en": (
        "⚠️ *CropRadar Outbreak Alert*\n\n"
        "Possible outbreak of *{disease}* detected near your area.\n"
        "We recorded *{count}* reports within 50 km in the last 48 hours.\n\n"
        "🛡️ Please inspect nearby crops, isolate affected plants, "
        "and begin preventive treatment early."
    ),
    "kn": (
        "⚠️ *ಕ್ರಾಪ್‌ರಾಡಾರ್ ರೋಗ ಹರಡುವಿಕೆ ಎಚ್ಚರಿಕೆ*\n\n"
        "ನಿಮ್ಮ ಪ್ರದೇಶದ ಬಳಿ *{disease}* ರೋಗ ಹರಡುವಿಕೆ ಪತ್ತೆಯಾಗಿದೆ.\n"
        "ಕಳೆದ 48 ಗಂಟೆಗಳಲ್ಲಿ 50 ಕಿ.ಮೀ ಒಳಗೆ *{count}* ವರದಿಗಳು ದಾಖಲಾಗಿವೆ.\n\n"
        "🛡️ ದಯವಿಟ್ಟು ಹತ್ತಿರದ ಬೆಳೆಗಳನ್ನು ಪರಿಶೀಲಿಸಿ, ಬಾಧಿತ ಸಸ್ಯಗಳನ್ನು "
        "ಪ್ರತ್ಯೇಕಿಸಿ ಮತ್ತು ತಡೆಗಟ್ಟುವ ಚಿಕಿತ್ಸೆ ಪ್ರಾರಂಭಿಸಿ."
    ),
}


def _format_alert(disease: str, count: int, language: str) -> str:
    template = ALERT_TEMPLATES.get(language, ALERT_TEMPLATES["en"])
    return template.format(disease=disease, count=count)


def broadcast_outbreak_alert(
    disease: str,
    count: int,
    users: list[dict],
) -> int:
    """
    Send an outbreak alert to a list of users.

    Parameters
    ----------
    disease : str   – disease name
    count   : int   – number of reports in the cluster
    users   : list  – dicts with at least 'chat_id' and 'language'

    Returns the number of messages successfully sent.
    """
    token = TELEGRAM_TOKEN
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set; cannot send broadcast.")
        return 0

    url = TELEGRAM_API.format(token=token)
    sent = 0

    for user in users:
        lang = user.get("language", "en")
        text = _format_alert(disease, count, lang)
        try:
            resp = requests.post(
                url,
                json={
                    "chat_id": user["chat_id"],
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            if resp.ok:
                sent += 1
            else:
                logger.warning(
                    "Telegram send failed for chat_id=%s: %s",
                    user["chat_id"], resp.text,
                )
        except Exception as exc:
            logger.warning(
                "Telegram send error for chat_id=%s: %s",
                user["chat_id"], exc,
            )

    logger.info(
        "Outbreak broadcast: disease=%s, eligible=%d, sent=%d",
        disease, len(users), sent,
    )
    return sent
