"""
bot.py - CropRadar Telegram bot (bilingual: English / Kannada)

Conversation flow:
  /start
    └─► Language choice (English / ಕನ್ನಡ)  [WAITING_LANGUAGE]
         └─► Ask for location               [WAITING_LOCATION]
              └─► Check nearby outbreaks
                   └─► Ask for crop type     [WAITING_CROP]
                        └─► Ask for photo    [WAITING_PHOTO]
                             └─► Diagnose → reply → loop back
"""

from dotenv import load_dotenv
load_dotenv()

import logging
import os
import tempfile
from pathlib import Path

import database as database
import crop_stage
import requests
import risk_features
import risk_model
import risk_report
from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
API_BASE_URL   = os.environ.get("CROPRADAR_API_URL", "http://localhost:8000")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_LANGUAGE = 0
WAITING_LOCATION = 1
WAITING_CROP     = 2
WAITING_PHOTO    = 3

# Trigger texts for language buttons
LANG_EN = "🇬🇧 English"
LANG_KN = "🇮🇳 ಕನ್ನಡ"

# Supported crop list (matches crop_stage.SUPPORTED_CROPS)
CROP_LIST = crop_stage.SUPPORTED_CROPS


# ---------------------------------------------------------------------------
# Bilingual string table
# ---------------------------------------------------------------------------

STRINGS = {
    "en": {
        "welcome": (
            "🌾 *Welcome to CropRadar!*\n\n"
            "I detect crop diseases from photos and alert you to outbreaks nearby.\n\n"
            "Please choose your language to continue:"
        ),
        "lang_set": "✅ Language set to *English*. Let's get started!\n\n",
        "ask_location": (
            "📍 *Step 1 — Share Your Location*\n\n"
            "Please share your current location so I can check for disease outbreaks "
            "in your area before we analyse your crop."
        ),
        "share_btn": "📍 Share My Location",
        "location_received": "✅ Location received — *{lat:.4f}°, {lon:.4f}°*\n\n🔍 Checking for disease outbreaks in your area…",
        "outbreak_header": "⚠️ *Outbreak Risk Alert!*\n\nThe following diseases have been reported near you recently:\n",
        "outbreak_row": "🦠 *{disease}* — {count} reports within 50 km",
        "outbreak_footer": "\n\n🛡️ Apply preventive treatment and monitor your crops closely.",
        "no_outbreak": "✅ *No active outbreaks detected near you.*",
        "ask_crop": (
            "\n\n🌱 *Step 2 — Select Your Crop*\n\n"
            "What crop are you growing? This helps us send you "
            "stage-specific risk advisories."
        ),
        "crop_set": "✅ Crop set to *{crop}*.\n\n",
        "ask_photo": "📸 *Step 3:* Send me a photo of your crop leaf and I'll diagnose it!",
        "analysing": "🔍 Analysing your crop image, please wait…",
        "diagnosis_header": "🌿 *CropRadar Diagnosis*",
        "disease_label": "🦠 *Disease:*",
        "confidence_label": "*Confidence:*",
        "remedy_label": "💊 *Remedy:*",
        "prevention_label": "🛡️ *Prevention:*",
        "report_stored": "📋 _Report #{id} stored{loc}_",
        "next_photo": "\n📸 Send another photo to analyse more crops, or /restart to reset.",
        "risk_analysing": "📊 Analysing crop risk for your area…",
        "conn_error": "❌ Could not connect to the CropRadar backend.\nMake sure the API is running at: {url}",
        "analysis_error": "❌ Analysis failed: {err}",
        "nudge_location": "⚠️ I need your *location* first — please tap the 📍 button below.",
        "nudge_photo": "📸 Please send a *photo* of a crop leaf to get a diagnosis.",
        "nudge_language": "Please choose a language using the buttons below:",
        "nudge_crop": "🌱 Please select your crop using the buttons below:",
        "session_ended": "Session ended. Type /start to begin again.",
    },
    "kn": {
        "welcome": (
            "🌾 *ಕ್ರಾಪ್‌ರಾಡಾರ್‌ಗೆ ಸ್ವಾಗತ!*\n\n"
            "ನಾನು ಫೋಟೋಗಳಿಂದ ಬೆಳೆ ರೋಗಗಳನ್ನು ಪತ್ತೆ ಮಾಡುತ್ತೇನೆ ಮತ್ತು ನಿಮ್ಮ ಸುತ್ತಲಿನ "
            "ರೋಗ ಹರಡುವಿಕೆ ಬಗ್ಗೆ ಎಚ್ಚರಿಸುತ್ತೇನೆ.\n\n"
            "ಮುಂದುವರಿಯಲು ಭಾಷೆಯನ್ನು ಆರಿಸಿ:"
        ),
        "lang_set": "✅ ಭಾಷೆಯನ್ನು *ಕನ್ನಡ*ಕ್ಕೆ ಹೊಂದಿಸಲಾಗಿದೆ. ಪ್ರಾರಂಭಿಸೋಣ!\n\n",
        "ask_location": (
            "📍 *ಹಂತ 1 — ನಿಮ್ಮ ಸ್ಥಳ ಹಂಚಿಕೊಳ್ಳಿ*\n\n"
            "ನಿಮ್ಮ ಬಳಿ ರೋಗ ಹರಡುವಿಕೆ ಇದೆಯೇ ಎಂದು ಪರಿಶೀಲಿಸಲು ದಯವಿಟ್ಟು "
            "ನಿಮ್ಮ ಪ್ರಸ್ತುತ ಸ್ಥಳವನ್ನು ಹಂಚಿಕೊಳ್ಳಿ."
        ),
        "share_btn": "📍 ನನ್ನ ಸ್ಥಳ ಹಂಚಿಕೊಳ್ಳಿ",
        "location_received": "✅ ಸ್ಥಳ ಸ್ವೀಕರಿಸಲಾಗಿದೆ — *{lat:.4f}°, {lon:.4f}°*\n\n🔍 ನಿಮ್ಮ ಪ್ರದೇಶದಲ್ಲಿ ರೋಗ ಹರಡುವಿಕೆ ಪರಿಶೀಲಿಸಲಾಗುತ್ತಿದೆ…",
        "outbreak_header": "⚠️ *ರೋಗ ಹರಡುವಿಕೆ ಎಚ್ಚರಿಕೆ!*\n\nಇತ್ತೀಚೆಗೆ ನಿಮ್ಮ ಬಳಿ ಈ ರೋಗಗಳು ವರದಿಯಾಗಿವೆ:\n",
        "outbreak_row": "🦠 *{disease}* — 50 ಕಿ.ಮೀ ಒಳಗೆ {count} ವರದಿಗಳು",
        "outbreak_footer": "\n\n🛡️ ತಡೆಗಟ್ಟುವ ಚಿಕಿತ್ಸೆ ಅನ್ವಯಿಸಿ ಮತ್ತು ನಿಮ್ಮ ಬೆಳೆಗಳನ್ನು ಗಮನಿಸಿ.",
        "no_outbreak": "✅ *ನಿಮ್ಮ ಬಳಿ ಯಾವುದೇ ರೋಗ ಹರಡುವಿಕೆ ಕಂಡುಬಂದಿಲ್ಲ.*",
        "ask_crop": (
            "\n\n🌱 *ಹಂತ 2 — ನಿಮ್ಮ ಬೆಳೆ ಆಯ್ಕೆ ಮಾಡಿ*\n\n"
            "ನೀವು ಯಾವ ಬೆಳೆ ಬೆಳೆಯುತ್ತಿದ್ದೀರಿ? ಈ ಮಾಹಿತಿ ಹಂತ-ನಿರ್ದಿಷ್ಟ "
            "ಅಪಾಯ ಸಲಹೆಗಳನ್ನು ಕಳುಹಿಸಲು ಸಹಾಯ ಮಾಡುತ್ತದೆ."
        ),
        "crop_set": "✅ ಬೆಳೆ *{crop}* ಗೆ ಹೊಂದಿಸಲಾಗಿದೆ.\n\n",
        "ask_photo": "📸 *ಹಂತ 3:* ರೋಗ ಪತ್ತೆಗಾಗಿ ನಿಮ್ಮ ಬೆಳೆ ಎಲೆಯ ಫೋಟೋ ಕಳುಹಿಸಿ!",
        "analysing": "🔍 ನಿಮ್ಮ ಬೆಳೆಯ ಚಿತ್ರ ವಿಶ್ಲೇಷಿಸಲಾಗುತ್ತಿದೆ, ದಯವಿಟ್ಟು ನಿರೀಕ್ಷಿಸಿ…",
        "diagnosis_header": "🌿 *ಕ್ರಾಪ್‌ರಾಡಾರ್ ರೋಗ ನಿರ್ಣಯ*",
        "disease_label": "🦠 *ರೋಗ:*",
        "confidence_label": "*ವಿಶ್ವಾಸ:*",
        "remedy_label": "💊 *ಪರಿಹಾರ:*",
        "prevention_label": "🛡️ *ತಡೆಗಟ್ಟುವಿಕೆ:*",
        "report_stored": "📋 _ವರದಿ #{id} ಸಂಗ್ರಹಿಸಲಾಗಿದೆ{loc}_",
        "next_photo": "\n📸 ಇನ್ನೊಂದು ಫೋಟೋ ಕಳುಹಿಸಿ ಅಥವಾ /restart ಮಾಡಿ.",
        "risk_analysing": "📊 ನಿಮ್ಮ ಪ್ರದೇಶದ ಬೆಳೆ ಅಪಾಯ ವಿಶ್ಲೇಷಿಸಲಾಗುತ್ತಿದೆ…",
        "conn_error": "❌ CropRadar ಬ್ಯಾಕೆಂಡ್‌ಗೆ ಸಂಪರ್ಕಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ.\n{url} ನಲ್ಲಿ API ಚಾಲನೆಯಲ್ಲಿದೆಯೇ ಎಂದು ಖಚಿತಪಡಿಸಿ.",
        "analysis_error": "❌ ವಿಶ್ಲೇಷಣೆ ವಿಫಲವಾಗಿದೆ: {err}",
        "nudge_location": "⚠️ ಮೊದಲು ನಿಮ್ಮ *ಸ್ಥಳ* ಬೇಕು — ದಯವಿಟ್ಟು ಕೆಳಗಿನ 📍 ಬಟನ್ ಅನ್ನು ಟ್ಯಾಪ್ ಮಾಡಿ.",
        "nudge_photo": "📸 ರೋಗ ನಿರ್ಣಯ ಪಡೆಯಲು ಬೆಳೆ ಎಲೆಯ *ಫೋಟೋ* ಕಳುಹಿಸಿ.",
        "nudge_language": "ದಯವಿಟ್ಟು ಕೆಳಗಿನ ಬಟನ್‌ಗಳನ್ನು ಬಳಸಿ ಭಾಷೆ ಆರಿಸಿ:",
        "nudge_crop": "🌱 ದಯವಿಟ್ಟು ಕೆಳಗಿನ ಬಟನ್‌ಗಳನ್ನು ಬಳಸಿ ಬೆಳೆ ಆಯ್ಕೆ ಮಾಡಿ:",
        "session_ended": "ಸೆಷನ್ ಮುಕ್ತಾಯವಾಗಿದೆ. ಮತ್ತೆ ಪ್ರಾರಂಭಿಸಲು /start ಟೈಪ್ ಮಾಡಿ.",
    },
}


def s(context: ContextTypes.DEFAULT_TYPE, key: str) -> str:
    """Return the string for the user's chosen language (defaults to English)."""
    lang = context.user_data.get("lang", "en")
    return STRINGS[lang][key]


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------

def _language_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(LANG_EN), KeyboardButton(LANG_KN)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _location_keyboard(lang: str) -> ReplyKeyboardMarkup:
    label = STRINGS[lang]["share_btn"]
    return ReplyKeyboardMarkup(
        [[KeyboardButton(label, request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _crop_keyboard() -> ReplyKeyboardMarkup:
    """Build a keyboard with crop type buttons (2 per row)."""
    buttons = []
    row = []
    for i, crop in enumerate(CROP_LIST):
        row.append(KeyboardButton(f"🌾 {crop}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return ReplyKeyboardMarkup(
        buttons, resize_keyboard=True, one_time_keyboard=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_nearby_outbreaks(lat: float, lon: float) -> list[dict]:
    try:
        r = requests.get(
            f"{API_BASE_URL}/nearby-alerts",
            params={"lat": lat, "lon": lon, "radius_km": 50},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("outbreaks", [])
    except Exception as exc:
        logger.warning("Could not fetch nearby alerts: %s", exc)
        return []


# ---------------------------------------------------------------------------
# State: WAITING_LANGUAGE  (entry point)
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show language selection buttons."""
    context.user_data.clear()
    await update.message.reply_text(
        STRINGS["en"]["welcome"],   # always shown in English first
        parse_mode="Markdown",
        reply_markup=_language_keyboard(),
    )
    return WAITING_LANGUAGE


async def handle_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the user's language choice, then ask for location."""
    text = update.message.text.strip()

    if LANG_KN in text:
        lang = "kn"
    else:
        lang = "en"

    context.user_data["lang"] = lang

    await update.message.reply_text(
        s(context, "lang_set") + s(context, "ask_location"),
        parse_mode="Markdown",
        reply_markup=_location_keyboard(lang),
    )
    return WAITING_LOCATION


async def wrong_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Nudge user to pick a language button."""
    await update.message.reply_text(
        s(context, "nudge_language"),
        reply_markup=_language_keyboard(),
    )
    return WAITING_LANGUAGE


# ---------------------------------------------------------------------------
# State: WAITING_LOCATION
# ---------------------------------------------------------------------------

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store location, persist user for broadcasts, and check for nearby outbreaks."""
    msg = update.message
    lat = msg.location.latitude
    lon = msg.location.longitude
    context.user_data["lat"] = lat
    context.user_data["lon"] = lon
    lang = context.user_data.get("lang", "en")

    # Persist / update user for proactive outbreak broadcasts
    try:
        database.upsert_bot_user(
            chat_id=update.effective_chat.id,
            telegram_user_id=update.effective_user.id,
            language=lang,
            latitude=lat,
            longitude=lon,
        )
    except Exception as exc:
        logger.warning("Failed to persist bot user: %s", exc)

    await msg.reply_text(
        s(context, "location_received").format(lat=lat, lon=lon),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )

    # --- Predictive area-risk analysis ---
    try:
        await msg.reply_text(s(context, "risk_analysing"))
        features = risk_features.build_risk_features(lat, lon)
        risk_result = risk_model.score_area_risk(features)
        report_msg = risk_report.build_crop_risk_report(lang, risk_result)
        await msg.reply_text(report_msg, parse_mode="Markdown")
    except Exception as exc:
        logger.warning("Predictive risk analysis failed: %s", exc)

    # --- Existing outbreak check ---
    outbreaks = _check_nearby_outbreaks(lat, lon)

    if outbreaks:
        lines = [s(context, "outbreak_header")]
        for ob in outbreaks:
            lines.append(s(context, "outbreak_row").format(
                disease=ob["disease_type"], count=ob["count"]
            ))
        lines.append(s(context, "outbreak_footer"))
        lines.append(s(context, "ask_crop"))
        await msg.reply_text(
            "\n".join(lines), parse_mode="Markdown",
            reply_markup=_crop_keyboard(),
        )
    else:
        await msg.reply_text(
            s(context, "no_outbreak") + s(context, "ask_crop"),
            parse_mode="Markdown",
            reply_markup=_crop_keyboard(),
        )

    return WAITING_CROP


async def wrong_input_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "en")
    await update.message.reply_text(
        s(context, "nudge_location"),
        parse_mode="Markdown",
        reply_markup=_location_keyboard(lang),
    )
    return WAITING_LOCATION


# ---------------------------------------------------------------------------
# State: WAITING_CROP
# ---------------------------------------------------------------------------

async def handle_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the crop type and proceed to photo stage."""
    text = update.message.text.strip()

    # Parse crop from button text (e.g. "🌾 Rice" → "Rice")
    crop_name = text.replace("🌾 ", "").strip()

    if crop_name not in CROP_LIST:
        await update.message.reply_text(
            s(context, "nudge_crop"),
            reply_markup=_crop_keyboard(),
        )
        return WAITING_CROP

    context.user_data["crop_type"] = crop_name

    # Persist crop type to database
    try:
        database.update_bot_user_crop(
            update.effective_chat.id, crop_name,
        )
    except Exception as exc:
        logger.warning("Failed to persist crop type: %s", exc)

    await update.message.reply_text(
        s(context, "crop_set").format(crop=crop_name) + s(context, "ask_photo"),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return WAITING_PHOTO


async def wrong_input_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Nudge user to pick a crop button."""
    await update.message.reply_text(
        s(context, "nudge_crop"),
        reply_markup=_crop_keyboard(),
    )
    return WAITING_CROP


# ---------------------------------------------------------------------------
# State: WAITING_PHOTO
# ---------------------------------------------------------------------------

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Analyse crop image and reply with diagnosis."""
    msg    = update.message
    lat    = context.user_data.get("lat")
    lon    = context.user_data.get("lon")

    await msg.reply_text(s(context, "analysing"))

    # Download photo
    photo   = msg.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        await tg_file.download_to_drive(tmp.name)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as img_file:
            form_data = {"language": context.user_data.get("lang", "en")}
            if lat is not None:
                form_data["latitude"]  = lat
                form_data["longitude"] = lon
            response = requests.post(
                f"{API_BASE_URL}/analyze-image",
                files={"file": ("crop.jpg", img_file, "image/jpeg")},
                data=form_data,
                timeout=60,
            )
        response.raise_for_status()
        result = response.json()
    except requests.exceptions.ConnectionError:
        await msg.reply_text(s(context, "conn_error").format(url=API_BASE_URL))
        return WAITING_PHOTO
    except Exception as exc:
        logger.error("API error: %s", exc)
        await msg.reply_text(s(context, "analysis_error").format(err=exc))
        return WAITING_PHOTO
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    disease    = result.get("disease_name", "Unknown")
    confidence = result.get("confidence", "Unknown")
    remedy     = result.get("remedy", "N/A")
    prevention = result.get("prevention", "N/A")
    alert      = result.get("outbreak_alert")
    report_id  = result.get("report_id")

    conf_emoji = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(confidence, "⚪")

    lines = [
        s(context, "diagnosis_header"), "",
        f"{s(context, 'disease_label')} {disease}",
        f"{conf_emoji} {s(context, 'confidence_label')} {confidence}", "",
        f"{s(context, 'remedy_label')}\n{remedy}", "",
        f"{s(context, 'prevention_label')}\n{prevention}",
    ]
    if report_id:
        loc_note = f" (📍 {lat:.4f}°, {lon:.4f}°)" if lat is not None else ""
        lines += ["", s(context, "report_stored").format(id=report_id, loc=loc_note)]
    if alert:
        lines += ["", "━━━━━━━━━━━━━━━━", alert]
    lines.append(s(context, "next_photo"))

    await msg.reply_text("\n".join(lines), parse_mode="Markdown")
    return WAITING_PHOTO


async def wrong_input_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        s(context, "nudge_photo"),
        parse_mode="Markdown",
    )
    return WAITING_PHOTO


# ---------------------------------------------------------------------------
# Cancel / restart
# ---------------------------------------------------------------------------

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        s(context, "session_ended"),
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN before running bot.py")

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start",   start),
            CommandHandler("restart", start),
        ],
        states={
            WAITING_LANGUAGE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & (
                        filters.Regex(LANG_EN) | filters.Regex("ಕನ್ನಡ")
                    ),
                    handle_language,
                ),
                MessageHandler(filters.TEXT & ~filters.COMMAND, wrong_language),
            ],
            WAITING_LOCATION: [
                MessageHandler(filters.LOCATION, handle_location),
                MessageHandler(filters.TEXT & ~filters.COMMAND, wrong_input_location),
            ],
            WAITING_CROP: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_crop,
                ),
            ],
            WAITING_PHOTO: [
                MessageHandler(filters.PHOTO, handle_photo),
                # Allow location refresh mid-session
                MessageHandler(filters.LOCATION, handle_location),
                MessageHandler(filters.TEXT & ~filters.COMMAND, wrong_input_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    application.add_handler(conv)
    logger.info("CropRadar bot starting (bilingual + crop profiling)…")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
