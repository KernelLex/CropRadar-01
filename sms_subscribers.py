"""
sms_subscribers.py — Onboarding State Machine for SMS Lite
Handles the step-by-step numeric flow for keypad phones.
States: awaiting_language -> awaiting_subscribe -> awaiting_pincode -> awaiting_crop -> subscribed -> unsubscribed
"""

import json
from pathlib import Path
import database
import sms_templates
from datetime import datetime

# Load PIN code lookup data
pincode_file = Path(__file__).parent / "pincode_data.json"
try:
    PINCODES = json.loads(pincode_file.read_text(encoding="utf-8"))
except Exception as e:
    print(f"Warning: Failed to load pincode_data.json: {e}")
    PINCODES = {}

# Constants
WAITING_LANG = "awaiting_language"
WAITING_SUB = "awaiting_subscribe"
WAITING_PIN = "awaiting_pincode"
WAITING_CROP = "awaiting_crop"
SUBSCRIBED = "subscribed"
UNSUBSCRIBED = "unsubscribed"

def process_incoming_sms(phone: str, body: str) -> str:
    """Main state machine entry point."""
    body = body.strip()
    
    # Load or create user
    sub = database.get_sms_subscriber(phone)
    if not sub:
        database.upsert_sms_subscriber(phone, onboarding_state=WAITING_LANG)
        return sms_templates.get_template("en", "LANGUAGE_PROMPT")

    state = sub.get("onboarding_state", WAITING_LANG)
    
    # Process based on current state
    if state == WAITING_LANG:
        return _handle_language(phone, sub, body)
    elif state == WAITING_SUB:
        return _handle_subscribe(phone, sub, body)
    elif state == WAITING_PIN:
        return _handle_pincode(phone, sub, body)
    elif state == WAITING_CROP:
        return _handle_crop(phone, sub, body)
    elif state == SUBSCRIBED:
        return _handle_subscribed(phone, sub, body)
    elif state == UNSUBSCRIBED:
        # Any message from an unsubscribed user restarts the flow
        database.update_sms_subscriber_state(phone, WAITING_LANG, is_active=0)
        return sms_templates.get_template("en", "LANGUAGE_PROMPT")
    
    # Fallback
    database.update_sms_subscriber_state(phone, WAITING_LANG)
    return sms_templates.get_template("en", "LANGUAGE_PROMPT")

def _handle_language(phone: str, sub: dict, body: str) -> str:
    if body == "2":
        database.update_sms_subscriber_state(phone, WAITING_SUB, language="en")
        return sms_templates.get_template("en", "SUBSCRIBE_PROMPT")
    elif body == "4":
        database.update_sms_subscriber_state(phone, WAITING_SUB, language="kn")
        return sms_templates.get_template("kn", "SUBSCRIBE_PROMPT")
    
    # Invalid input
    lang = sub.get("language", "en")
    database.update_sms_subscriber_state(phone, WAITING_LANG) # ensure state is set
    return sms_templates.get_template(lang, "LANGUAGE_PROMPT")

def _handle_subscribe(phone: str, sub: dict, body: str) -> str:
    lang = sub.get("language", "en")
    
    if body == "1":
        database.update_sms_subscriber_state(phone, WAITING_PIN)
        return sms_templates.get_template(lang, "PINCODE_PROMPT")
    elif body == "0":
        database.update_sms_subscriber_state(phone, UNSUBSCRIBED, subscription_status="cancelled", is_active=0)
        return sms_templates.get_template(lang, "UNSUBSCRIBE")
    
    # Invalid input
    return sms_templates.get_template(lang, "INVALID_INPUT") + "\n" + sms_templates.get_template(lang, "SUBSCRIBE_PROMPT")

def _handle_pincode(phone: str, sub: dict, body: str) -> str:
    lang = sub.get("language", "en")
    
    if len(body) == 6 and body.isdigit():
        # Look up PIN code
        loc = PINCODES.get(body)
        if not loc:
            # Try fallback by first two digits (e.g. Karnataka = 56, 57, 58, 59)
            fallback_key = f"default_{body[:2]}"
            loc = PINCODES.get(fallback_key)
            
        if loc:
            database.update_sms_subscriber_state(
                phone, 
                WAITING_CROP, 
                pincode=body,
                district=loc["district"],
                state=loc["state"],
                latitude=loc["lat"],
                longitude=loc["lon"]
            )
            return sms_templates.get_template(lang, "CROP_PROMPT")
    
    # Invalid or unknown input (for hackathon, we force valid PIN to proceed, keep it simple)
    # If standard 6 digit fails to fallback, just accept it and use a generic default if no match at all
    if len(body) == 6 and body.isdigit():
        # Generic fallback
        database.update_sms_subscriber_state(
            phone, 
            WAITING_CROP, 
            pincode=body,
            district="Unknown",
            state="Unknown",
            latitude=15.3173, # Central karnataka
            longitude=75.7139
        )
        return sms_templates.get_template(lang, "CROP_PROMPT")

    return sms_templates.get_template(lang, "INVALID_INPUT") + "\n" + sms_templates.get_template(lang, "PINCODE_PROMPT")

def _handle_crop(phone: str, sub: dict, body: str) -> str:
    lang = sub.get("language", "en")
    
    if body.isdigit():
        idx = int(body)
        if idx in sms_templates.CROP_MAP:
            crop_name = sms_templates.CROP_MAP[idx]
            database.update_sms_subscriber_state(
                phone, 
                SUBSCRIBED, 
                crop_type=crop_name,
                subscription_status="active",
                is_active=1
            )
            return sms_templates.get_template(lang, "SUCCESS")
            
    return sms_templates.get_template(lang, "INVALID_INPUT") + "\n" + sms_templates.get_template(lang, "CROP_PROMPT")

def _handle_subscribed(phone: str, sub: dict, body: str) -> str:
    lang = sub.get("language", "en")
    
    if body == "0":
        database.update_sms_subscriber_state(phone, UNSUBSCRIBED, subscription_status="cancelled", is_active=0)
        return sms_templates.get_template(lang, "UNSUBSCRIBE")
        
    return sms_templates.get_template(lang, "INVALID_INPUT") + "\nTo unsubscribe, reply 0."
