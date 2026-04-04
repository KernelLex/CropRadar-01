"""
broadcast_all.py — Send a test notification to ALL registered users.

Channels:
  1. Telegram  — all bot_users
  2. WhatsApp  — all whatsapp_users
  3. App push  — all app_devices (FCM)

Usage:
  python broadcast_all.py
"""

import json
import os
import sqlite3
import time
from pathlib import Path

from dotenv import load_dotenv
import requests

load_dotenv()

DB_PATH            = str(Path(__file__).resolve().parent / "cropradar.db")
TELEGRAM_TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_WA_NUMBER   = "whatsapp:+14155238886"
SA_PATH            = Path(__file__).resolve().parent / "firebase-adminsdk-account.json"

DISEASE   = "Leaf Blight"
COUNT     = 5

MSG_EN = (
    "⚠️ *CropRadar Test Alert*\n\n"
    f"This is a test broadcast from CropRadar.\n"
    f"Possible outbreak of *{DISEASE}* detected near your area.\n"
    f"{COUNT} reports within 50 km in the last 48 hours.\n\n"
    "🛡️ Inspect nearby crops, isolate affected plants, "
    "and begin preventive treatment early."
)

MSG_KN = (
    "⚠️ *ಕ್ರಾಪ್‌ರಾಡಾರ್ ಪರೀಕ್ಷಾ ಎಚ್ಚರಿಕೆ*\n\n"
    f"ಇದು ಕ್ರಾಪ್‌ರಾಡಾರ್‌ನಿಂದ ಪರೀಕ್ಷಾ ಸಂದೇಶ.\n"
    f"ನಿಮ್ಮ ಪ್ರದೇಶದ ಬಳಿ *{DISEASE}* ರೋಗ ಹರಡುವಿಕೆ ಪತ್ತೆಯಾಗಿದೆ.\n"
    f"ಕಳೆದ 48 ಗಂಟೆಗಳಲ್ಲಿ 50 ಕಿ.ಮೀ ಒಳಗೆ {COUNT} ವರದಿಗಳು.\n\n"
    "🛡️ ಬೆಳೆಗಳನ್ನು ಪರಿಶೀಲಿಸಿ, ಬಾಧಿತ ಸಸ್ಯಗಳನ್ನು ಪ್ರತ್ಯೇಕಿಸಿ "
    "ಮತ್ತು ತಡೆಗಟ್ಟುವ ಚಿಕಿತ್ಸೆ ಪ್ರಾರಂಭಿಸಿ."
)

def get_msg(lang):
    return MSG_KN if lang == "kn" else MSG_EN


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def get_all_telegram_users():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT chat_id, language FROM bot_users WHERE is_active=1").fetchall()
    con.close()
    return [dict(r) for r in rows]

def get_all_whatsapp_users():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT wa_number, language FROM whatsapp_users").fetchall()
    con.close()
    return [dict(r) for r in rows]

def get_all_app_devices():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT fcm_token, language FROM app_devices").fetchall()
    con.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Channel 1 — Telegram
# ---------------------------------------------------------------------------
def broadcast_telegram(users):
    if not TELEGRAM_TOKEN:
        print("[Telegram] No token set — skipping.")
        return 0
    if not users:
        print("[Telegram] No users registered.")
        return 0
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    sent = 0
    for u in users:
        try:
            r = requests.post(url, json={
                "chat_id":    u["chat_id"],
                "text":       get_msg(u.get("language", "en")),
                "parse_mode": "Markdown",
            }, timeout=10)
            if r.ok:
                sent += 1
                print(f"  [Telegram] Sent to chat_id={u['chat_id']}")
            else:
                print(f"  [Telegram] FAILED chat_id={u['chat_id']}: {r.text[:120]}")
        except Exception as e:
            print(f"  [Telegram] ERROR: {e}")
    return sent


# ---------------------------------------------------------------------------
# Channel 2 — WhatsApp (Twilio)
# ---------------------------------------------------------------------------
def broadcast_whatsapp(users):
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("[WhatsApp] No Twilio credentials — skipping.")
        return 0
    if not users:
        print("[WhatsApp] No users registered.")
        return 0
    url  = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    sent = 0
    for u in users:
        text = get_msg(u.get("language", "en")).replace("*", "")
        try:
            r = requests.post(url,
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                data={"From": TWILIO_WA_NUMBER, "To": u["wa_number"], "Body": text},
                timeout=15)
            if r.ok:
                sent += 1
                print(f"  [WhatsApp] Sent to {u['wa_number']}")
            else:
                print(f"  [WhatsApp] FAILED {u['wa_number']}: {r.text[:120]}")
        except Exception as e:
            print(f"  [WhatsApp] ERROR: {e}")
    return sent


# ---------------------------------------------------------------------------
# Channel 3 — FCM Push
# ---------------------------------------------------------------------------
_fcm_cache: dict = {}

def _get_fcm_token():
    if not SA_PATH.exists():
        print("[FCM] firebase-adminsdk-account.json not found — skipping.")
        return None
    now    = time.time()
    cached = _fcm_cache.get("token")
    if cached and now < _fcm_cache.get("expires", 0):
        return cached
    try:
        import base64
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        sa  = json.loads(SA_PATH.read_text())
        iat = int(now)
        exp = iat + 3600
        header  = base64.urlsafe_b64encode(json.dumps({"alg":"RS256","typ":"JWT"}).encode()).rstrip(b"=").decode()
        claims  = {"iss": sa["client_email"],
                   "scope": "https://www.googleapis.com/auth/firebase.messaging",
                   "aud": "https://oauth2.googleapis.com/token",
                   "iat": iat, "exp": exp}
        payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        signing = f"{header}.{payload}".encode()
        key     = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
        sig     = base64.urlsafe_b64encode(key.sign(signing, padding.PKCS1v15(), hashes.SHA256())).rstrip(b"=").decode()
        jwt     = f"{header}.{payload}.{sig}"

        r = requests.post("https://oauth2.googleapis.com/token",
                          data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": jwt},
                          timeout=10)
        r.raise_for_status()
        token = r.json()["access_token"]
        _fcm_cache["token"]   = token
        _fcm_cache["expires"] = now + r.json().get("expires_in", 3600) - 60
        return token
    except Exception as e:
        print(f"[FCM] Token error: {e}")
        return None

def broadcast_fcm(devices):
    if not devices:
        print("[FCM] No devices registered.")
        return 0
    token = _get_fcm_token()
    if not token:
        return 0
    sa         = json.loads(SA_PATH.read_text())
    project_id = sa["project_id"]
    url        = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    headers    = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    sent       = 0
    for d in devices:
        fcm_token = d.get("fcm_token")
        if not fcm_token:
            continue
        payload = {"message": {
            "token": fcm_token,
            "notification": {
                "title": "CropRadar Test Alert",
                "body":  f"{DISEASE} detected near you — {COUNT} reports within 50 km.",
            },
            "data": {"disease": DISEASE, "count": str(COUNT), "type": "outbreak_alert"},
            "android": {"priority": "high", "notification": {"sound": "default"}},
        }}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            if r.ok:
                sent += 1
                print(f"  [FCM] Sent to token ...{fcm_token[-8:]}")
            else:
                print(f"  [FCM] FAILED ...{fcm_token[-8:]}: {r.text[:120]}")
        except Exception as e:
            print(f"  [FCM] ERROR: {e}")
    return sent


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n========================================")
    print("  CropRadar — Broadcast to ALL users")
    print("========================================\n")

    tg_users = get_all_telegram_users()
    wa_users = get_all_whatsapp_users()
    devices  = get_all_app_devices()

    print(f"Found: {len(tg_users)} Telegram | {len(wa_users)} WhatsApp | {len(devices)} App devices\n")

    print("[1/3] Broadcasting to Telegram...")
    tg = broadcast_telegram(tg_users)

    print(f"\n[2/3] Broadcasting to WhatsApp...")
    wa = broadcast_whatsapp(wa_users)

    print(f"\n[3/3] Broadcasting to App (FCM)...")
    fcm = broadcast_fcm(devices)

    print(f"\n========================================")
    print(f"  Done! Sent: Telegram={tg}  WhatsApp={wa}  FCM={fcm}")
    print(f"========================================\n")
