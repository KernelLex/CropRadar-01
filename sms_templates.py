"""
sms_templates.py — SMS message templates for CropRadar SMS Lite
All messages are kept short for keypad phones (≤160 chars where possible).
Supports English (en) and Kannada (kn).
"""

# Map digits 1-10 to crop types
CROP_MAP = {
    1: "Rice", 2: "Wheat", 3: "Tomato", 4: "Potato", 5: "Maize",
    6: "Cotton", 7: "Sorghum", 8: "Sugarcane", 9: "Chili", 10: "Mango"
}

# English templates
EN = {
    "LANGUAGE_PROMPT":   "Welcome to CropRadar. Reply 2 for English. Reply 4 for Kannada.",
    "SUBSCRIBE_PROMPT":  "Reply 1 to subscribe to CropRadar alerts. Reply 0 to cancel.",
    "PINCODE_PROMPT":    "Reply with your 6-digit PIN code to receive local crop alerts.",
    "CROP_PROMPT":       "Reply with crop number: " + ", ".join(f"{k} {v}" for k, v in CROP_MAP.items()),
    "SUCCESS":           "CropRadar alerts activated for your area. You will receive disease risk and outbreak warnings.",
    "INVALID_INPUT":     "Invalid reply. Please follow the instructions in the previous message.",
    "UNSUBSCRIBE":       "You have been unsubscribed from CropRadar SMS alerts. Send any message to start again.",
    "RISK_ALERT":        "CropRadar: {risk_level} disease risk detected in your area for {crop}. Please inspect crops and take preventive action.",
    "OUTBREAK_ALERT":    "CropRadar: Outbreak reported near your area affecting {crop} crops. Inspect fields and take precautions."
}

# Kannada templates
KN = {
    "LANGUAGE_PROMPT":   "ಕ್ರಾಪ್‌ರಾಡಾರ್‌ಗೆ ಸ್ವಾಗತ. English ಗಾಗಿ 2 ಉತ್ತರಿಸಿ. ಕನ್ನಡಕ್ಕಾಗಿ 4 ಉತ್ತರಿಸಿ.",
    "SUBSCRIBE_PROMPT":  "ಕ್ರಾಪ್‌ರಾಡಾರ್ ಎಚ್ಚರಿಕೆಗಳನ್ನು ಪಡೆಯಲು 1 ಉತ್ತರಿಸಿ. ರದ್ದುಗೊಳಿಸಲು 0 ಉತ್ತರಿಸಿ.",
    "PINCODE_PROMPT":    "ಸ್ಥಳೀಯ ಎಚ್ಚರಿಕೆಗಳನ್ನು ಪಡೆಯಲು ನಿಮ್ಮ 6-ಅಂಕಿಯ ಪಿನ್ ಕೋಡ್ ಉತ್ತರಿಸಿ.",
    "CROP_PROMPT":       "ಬೆಳೆ ಸಂಖ್ಯೆಯನ್ನು ಉತ್ತರಿಸಿ: " + ", ".join(f"{k} {v}" for k, v in CROP_MAP.items()),
    "SUCCESS":           "ನಿಮ್ಮ ಪ್ರದೇಶಕ್ಕೆ ಕ್ರಾಪ್‌ರಾಡಾರ್ ಸಕ್ರಿಯಗೊಳಿಸಲಾಗಿದೆ. ನೀವು ರೋಗದ ಅಪಾಯ ಮತ್ತು ಹರಡುವಿಕೆಯ ಎಚ್ಚರಿಕೆಗಳನ್ನು ಪಡೆಯುತ್ತೀರಿ.",
    "INVALID_INPUT":     "ತಪ್ಪಾದ ಉತ್ತರ. ದಯವಿಟ್ಟು ಹಿಂದಿನ ಸಂದೇಶದಲ್ಲಿನ ಸೂಚನೆಗಳನ್ನು ಪಾಲಿಸಿ.",
    "UNSUBSCRIBE":       "ಕ್ರಾಪ್‌ರಾಡಾರ್ SMS ನಿಂದ ಅನ್‌ಸಬ್‌ಸ್ಕ್ರೈಬ್ ಮಾಡಲಾಗಿದೆ. ಮತ್ತೆ ಪ್ರಾರಂಭಿಸಲು ಯಾವುದೇ ಸಂದೇಶ ಕಳುಹಿಸಿ.",
    "RISK_ALERT":        "ಕ್ರಾಪ್‌ರಾಡಾರ್: ನಿಮ್ಮ ಪ್ರದೇಶದಲ್ಲಿ {crop} ಬೆಳೆಗೆ {risk_level} ರೋಗದ ಅಪಾಯವಿದೆ. ಬೆಳೆಗಳನ್ನು ಪರಿಶೀಲಿಸಿ ಮುನ್ನೆಚ್ಚರಿಕೆ ವಹಿಸಿ.",
    "OUTBREAK_ALERT":    "ಕ್ರಾಪ್‌ರಾಡಾರ್: ನಿಮ್ಮ ಪ್ರದೇಶದ ಬಳಿ {crop} ಬೆಳೆಗೆ ರೋಗ ಹರಡುವಿಕೆ ವರದಿಯಾಗಿದೆ. ಬೆಳೆಗಳನ್ನು ಪರಿಶೀಲಿಸಿ."
}

def get_template(lang: str, key: str, **kwargs) -> str:
    """Helper to get a formatted template string."""
    strings = KN if lang == 'kn' else EN
    text = strings.get(key, EN.get(key, ""))
    return text.format(**kwargs) if kwargs else text
