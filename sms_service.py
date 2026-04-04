"""
sms_service.py — SMS Provider Wrapper
Abstracts sending SMS messages via Twilio, with local fallback logging.
"""

import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SMS_PROVIDER = os.getenv("SMS_PROVIDER", "log_only").lower()
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
SMS_SENDER_NUMBER = os.getenv("SMS_SENDER_NUMBER", "+1234567890")

def send_sms(phone_number: str, message: str) -> bool:
    """
    Send an SMS message using the configured provider.
    Fails gracefully and logs the result.
    """
    if not phone_number or not message:
        return False
        
    try:
        if SMS_PROVIDER == "twilio":
            return _send_twilio(phone_number, message)
        elif SMS_PROVIDER == "fast2sms":
            return _send_fast2sms(phone_number, message)
        else:
            return _send_log_only(phone_number, message)
    except Exception as e:
        logger.error(f"Failed to send SMS to {phone_number} via {SMS_PROVIDER}: {e}")
        return False

def _send_log_only(phone_number: str, message: str) -> bool:
    """Mock provider for local testing and dry-runs."""
    print(f"\n[SMS:LOG_ONLY] 📱 To: {phone_number}\n[Message]: {message}\n")
    logger.info(f"SMS logged (not sent) to {phone_number}")
    return True

def _send_twilio(phone_number: str, message: str) -> bool:
    """Send SMS via Twilio programmable SMS."""
    if not TWILIO_SID or not TWILIO_TOKEN:
        logger.warning("Twilio credentials missing. Falling back to log_only.")
        return _send_log_only(phone_number, message)
        
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
    
    resp = requests.post(
        url,
        auth=(TWILIO_SID, TWILIO_TOKEN),
        data={
            "From": SMS_SENDER_NUMBER,
            "To": phone_number,
            "Body": message
        },
        timeout=10
    )
    
    if resp.ok:
        logger.info(f"Twilio SMS sent successfully to {phone_number}")
        return True
    else:
        logger.error(f"Twilio SMS fail {phone_number}: {resp.text}")
        return False

def _send_fast2sms(phone_number: str, message: str) -> bool:
    """Stub for Fast2SMS for Indian traffic."""
    api_key = os.getenv("FAST2SMS_API_KEY")
    if not api_key:
        logger.warning("Fast2SMS API key missing. Falling back to log_only.")
        return _send_log_only(phone_number, message)
        
    url = "https://www.fast2sms.com/dev/bulkV2"
    headers = {"authorization": api_key, "Content-Type": "application/x-www-form-urlencoded"}
    payload = f"route=q&message={message}&flash=0&numbers={phone_number}"
    
    resp = requests.post(url, data=payload, headers=headers, timeout=10)
    
    if resp.ok and resp.json().get("return"):
        logger.info(f"Fast2SMS SMS sent successfully to {phone_number}")
        return True
    else:
        logger.error(f"Fast2SMS SMS fail {phone_number}: {resp.text}")
        return False
