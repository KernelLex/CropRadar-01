"""
crop_stage.py - Crop growth stage estimation for CropRadar.

Estimates the current growth stage of a user's crop based on the crop type
and the registration date (when they first interacted with the bot).

Used by the weekly scheduler to send growth-stage-specific advisories.
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Crop growth calendars: list of (stage_name, duration_days)
# ---------------------------------------------------------------------------

CROP_STAGES = {
    "Rice": [
        ("Seedling", 21),
        ("Tillering", 25),
        ("Booting", 20),
        ("Flowering", 15),
        ("Grain Filling", 30),
        ("Maturity", 20),
    ],
    "Wheat": [
        ("Seedling", 20),
        ("Tillering", 30),
        ("Jointing", 20),
        ("Heading", 15),
        ("Grain Filling", 25),
        ("Maturity", 20),
    ],
    "Tomato": [
        ("Seedling", 25),
        ("Vegetative", 30),
        ("Flowering", 20),
        ("Fruiting", 30),
        ("Maturity", 15),
    ],
    "Potato": [
        ("Sprout Development", 20),
        ("Vegetative Growth", 25),
        ("Tuber Initiation", 15),
        ("Tuber Bulking", 30),
        ("Maturity", 20),
    ],
    "Maize": [
        ("Emergence", 14),
        ("Vegetative", 30),
        ("Tasseling", 15),
        ("Silking", 10),
        ("Grain Fill", 35),
        ("Maturity", 20),
    ],
    "Cotton": [
        ("Seedling", 20),
        ("Vegetative", 35),
        ("Square Formation", 20),
        ("Flowering", 25),
        ("Boll Development", 30),
        ("Maturity", 25),
    ],
    "Sorghum": [
        ("Emergence", 14),
        ("Vegetative", 30),
        ("Booting", 15),
        ("Flowering", 10),
        ("Grain Fill", 25),
        ("Maturity", 20),
    ],
    "Sugarcane": [
        ("Germination", 30),
        ("Tillering", 45),
        ("Grand Growth", 90),
        ("Maturity", 60),
    ],
    "Chili": [
        ("Seedling", 25),
        ("Vegetative", 30),
        ("Flowering", 20),
        ("Fruiting", 35),
        ("Maturity", 15),
    ],
    "Mango": [
        ("Vegetative Flush", 30),
        ("Flower Induction", 20),
        ("Flowering", 15),
        ("Fruit Set", 25),
        ("Fruit Development", 60),
        ("Maturity", 30),
    ],
}

# Default fallback for unknown crops
DEFAULT_STAGES = [
    ("Seedling", 25),
    ("Vegetative", 35),
    ("Flowering", 20),
    ("Fruiting", 30),
    ("Maturity", 20),
]

# ---------------------------------------------------------------------------
# Stage-specific risk advisories (bilingual)
# ---------------------------------------------------------------------------

STAGE_RISKS = {
    "Seedling": {
        "en": [
            "Seedlings are vulnerable to damping-off disease",
            "Ensure proper drainage to prevent root rot",
            "Monitor for cutworm and grasshopper damage",
        ],
        "kn": [
            "ಸಸಿಗಳು ಡ್ಯಾಂಪಿಂಗ್-ಆಫ್ ರೋಗಕ್ಕೆ ದುರ್ಬಲವಾಗಿವೆ",
            "ಬೇರು ಕೊಳೆತವನ್ನು ತಡೆಯಲು ಸರಿಯಾದ ಒಳಚರಂಡಿ ಖಚಿತಪಡಿಸಿ",
            "ಕಟ್‌ವರ್ಮ್ ಮತ್ತು ಮಿಡತೆ ಹಾನಿಗಾಗಿ ಗಮನಿಸಿ",
        ],
    },
    "Vegetative": {
        "en": [
            "High pest activity expected during rapid growth",
            "Monitor for aphids, whiteflies, and leaf miners",
            "Ensure adequate nitrogen for healthy foliage",
        ],
        "kn": [
            "ತ್ವರಿತ ಬೆಳವಣಿಗೆಯ ಸಮಯದಲ್ಲಿ ಹೆಚ್ಚಿನ ಕೀಟ ಚಟುವಟಿಕೆ ನಿರೀಕ್ಷಿಸಿ",
            "ಅಫಿಡ್, ಬಿಳಿ ನೊಣ ಮತ್ತು ಎಲೆ ಮೈನರ್‌ಗಳನ್ನು ಗಮನಿಸಿ",
            "ಆರೋಗ್ಯಕರ ಎಲೆಗಳಿಗೆ ಸಾಕಷ್ಟು ಸಾರಜನಕ ಖಚಿತಪಡಿಸಿ",
        ],
    },
    "Flowering": {
        "en": [
            "Critical stage — avoid pesticide spraying during bloom",
            "Monitor for flower drop and pollination issues",
            "Fungal infections are highly likely in humid conditions",
        ],
        "kn": [
            "ನಿರ್ಣಾಯಕ ಹಂತ — ಹೂಬಿಡುವ ಸಮಯದಲ್ಲಿ ಕೀಟನಾಶಕ ಸಿಂಪಡಿಸಬೇಡಿ",
            "ಹೂ ಉದುರುವಿಕೆ ಮತ್ತು ಪರಾಗಸ್ಪರ್ಶ ಸಮಸ್ಯೆಗಳನ್ನು ಗಮನಿಸಿ",
            "ತೇವಾಂಶ ಪರಿಸ್ಥಿತಿಗಳಲ್ಲಿ ಶಿಲೀಂಧ್ರ ಸೋಂಕು ಹೆಚ್ಚು ಸಾಧ್ಯ",
        ],
    },
    "Fruiting": {
        "en": [
            "Fruit borers and sucking pests are the biggest threat now",
            "Ensure adequate potassium for fruit development",
            "Watch for fruit rot in wet conditions",
        ],
        "kn": [
            "ಹಣ್ಣು ಕೊರೆಯುವ ಕೀಟಗಳು ಮತ್ತು ಹೀರುವ ಕೀಟಗಳು ಈಗ ದೊಡ್ಡ ಅಪಾಯ",
            "ಹಣ್ಣಿನ ಬೆಳವಣಿಗೆಗೆ ಸಾಕಷ್ಟು ಪೊಟ್ಯಾಸಿಯಂ ಖಚಿತಪಡಿಸಿ",
            "ಆರ್ದ್ರ ಪರಿಸ್ಥಿತಿಗಳಲ್ಲಿ ಹಣ್ಣು ಕೊಳೆಯುವಿಕೆ ಗಮನಿಸಿ",
        ],
    },
    "Maturity": {
        "en": [
            "Harvest timing is critical — over-maturity reduces quality",
            "Monitor for storage pest activity before harvest",
            "Reduce irrigation to prepare for harvest",
        ],
        "kn": [
            "ಕೊಯ್ಲು ಸಮಯ ನಿರ್ಣಾಯಕ — ಅತಿಯಾದ ಪಕ್ವತೆ ಗುಣಮಟ್ಟ ಕಡಿಮೆ ಮಾಡುತ್ತದೆ",
            "ಕೊಯ್ಲಿಗೆ ಮುಂಚೆ ಸಂಗ್ರಹ ಕೀಟ ಚಟುವಟಿಕೆ ಗಮನಿಸಿ",
            "ಕೊಯ್ಲಿಗೆ ತಯಾರಿಗಾಗಿ ನೀರಾವರಿ ಕಡಿಮೆ ಮಾಡಿ",
        ],
    },
    "Tillering": {
        "en": [
            "Active tiller production — maintain water level in paddy",
            "Apply top-dressing of nitrogen fertilizer",
            "Monitor for stem borer and brown plant hopper",
        ],
        "kn": [
            "ಸಕ್ರಿಯ ಟಿಲ್ಲರ್ ಉತ್ಪಾದನೆ — ಗದ್ದೆಯಲ್ಲಿ ನೀರಿನ ಮಟ್ಟ ಕಾಪಾಡಿ",
            "ಸಾರಜನಕ ಗೊಬ್ಬರದ ಟಾಪ್-ಡ್ರೆಸ್ಸಿಂಗ್ ಅನ್ವಯಿಸಿ",
            "ಕಾಂಡ ಕೊರಕ ಮತ್ತು ಕಂದು ಸಸ್ಯ ಜಿಗಿಯುವ ಕೀಟ ಗಮನಿಸಿ",
        ],
    },
    "Booting": {
        "en": [
            "Panicle forming — critical water and nutrient stage",
            "Blast disease risk is highest at this stage",
            "Apply potassium-based fertilizer for grain quality",
        ],
        "kn": [
            "ಪ್ಯಾನಿಕಲ್ ರಚನೆ — ನೀರು ಮತ್ತು ಪೋಷಕಾಂಶವು ನಿರ್ಣಾಯಕ",
            "ಈ ಹಂತದಲ್ಲಿ ಬ್ಲಾಸ್ಟ್ ರೋಗ ಅಪಾಯ ಹೆಚ್ಚು",
            "ಧಾನ್ಯ ಗುಣಮಟ್ಟಕ್ಕಾಗಿ ಪೊಟ್ಯಾಸಿಯಂ ಆಧಾರಿತ ಗೊಬ್ಬರ ಹಾಕಿ",
        ],
    },
    "Grain Filling": {
        "en": [
            "Grain weight building — do not stress the crop",
            "Watch for head blight and grain discoloration",
            "Avoid excess nitrogen at this stage",
        ],
        "kn": [
            "ಧಾನ್ಯ ತೂಕ ಹೆಚ್ಚುತ್ತಿದೆ — ಬೆಳೆಗೆ ಒತ್ತಡ ಹಾಕಬೇಡಿ",
            "ತಲೆ ಕೊಳೆತ ಮತ್ತು ಧಾನ್ಯ ಬಣ್ಣ ಬದಲಾವಣೆ ಗಮನಿಸಿ",
            "ಈ ಹಂತದಲ್ಲಿ ಅತಿಯಾದ ಸಾರಜನಕ ತಪ್ಪಿಸಿ",
        ],
    },
    "Grain Fill": {
        "en": [
            "Grain weight building — do not stress the crop",
            "Watch for head blight and grain discoloration",
            "Avoid excess nitrogen at this stage",
        ],
        "kn": [
            "ಧಾನ್ಯ ತೂಕ ಹೆಚ್ಚುತ್ತಿದೆ — ಬೆಳೆಗೆ ಒತ್ತಡ ಹಾಕಬೇಡಿ",
            "ತಲೆ ಕೊಳೆತ ಮತ್ತು ಧಾನ್ಯ ಬಣ್ಣ ಬದಲಾವಣೆ ಗಮನಿಸಿ",
            "ಈ ಹಂತದಲ್ಲಿ ಅತಿಯಾದ ಸಾರಜನಕ ತಪ್ಪಿಸಿ",
        ],
    },
}


# ---------------------------------------------------------------------------
# Stage estimation
# ---------------------------------------------------------------------------

def estimate_growth_stage(
    crop_type: str,
    registered_at: Optional[str],
) -> Optional[dict]:
    """
    Estimate the current growth stage of a crop.

    Args:
        crop_type: e.g. "Rice", "Wheat"
        registered_at: ISO date string when the user first registered

    Returns:
        dict with: stage_name, day_in_stage, total_days, stage_index,
                   total_stages, progress_pct, next_stage
        Or None if crop_type unknown or registered_at missing.
    """
    if not crop_type or not registered_at:
        return None

    stages = CROP_STAGES.get(crop_type, DEFAULT_STAGES)

    try:
        reg_date = datetime.fromisoformat(registered_at)
    except (ValueError, TypeError):
        return None

    days_since = (datetime.utcnow() - reg_date).days
    if days_since < 0:
        days_since = 0

    total_crop_duration = sum(d for _, d in stages)

    # Cycle if the crop has exceeded its total duration
    effective_days = days_since % total_crop_duration if total_crop_duration > 0 else 0

    cumulative = 0
    for i, (stage_name, duration) in enumerate(stages):
        if effective_days < cumulative + duration:
            day_in_stage = effective_days - cumulative
            next_stage = stages[i + 1][0] if i + 1 < len(stages) else "Harvest"
            progress_pct = round(
                (effective_days / total_crop_duration) * 100, 1
            )
            return {
                "crop_type": crop_type,
                "stage_name": stage_name,
                "stage_index": i + 1,
                "total_stages": len(stages),
                "day_in_stage": day_in_stage,
                "stage_duration": duration,
                "days_since_registration": days_since,
                "total_crop_duration": total_crop_duration,
                "progress_pct": progress_pct,
                "next_stage": next_stage,
            }
        cumulative += duration

    # Should not reach here, but fallback to last stage
    return {
        "crop_type": crop_type,
        "stage_name": stages[-1][0],
        "stage_index": len(stages),
        "total_stages": len(stages),
        "day_in_stage": 0,
        "stage_duration": stages[-1][1],
        "days_since_registration": days_since,
        "total_crop_duration": total_crop_duration,
        "progress_pct": 100.0,
        "next_stage": "Harvest",
    }


def get_stage_specific_risks(
    crop_type: str, stage_name: str, language: str = "en"
) -> list[str]:
    """
    Get risk advisories specific to a crop's growth stage.

    Falls back to generic stage risks if no crop-specific risks exist,
    then to the Vegetative stage as a default.
    """
    risks = STAGE_RISKS.get(stage_name, STAGE_RISKS.get("Vegetative", {}))
    return risks.get(language, risks.get("en", []))


# ---------------------------------------------------------------------------
# Bilingual stage report
# ---------------------------------------------------------------------------

def build_stage_report(language: str, stage_info: dict) -> str:
    """Build a bilingual weekly crop stage advisory message."""
    if language == "kn":
        return _build_stage_report_kn(stage_info)
    return _build_stage_report_en(stage_info)


def _build_stage_report_en(info: dict) -> str:
    crop = info.get("crop_type", "Crop")
    stage = info.get("stage_name", "Unknown")
    idx = info.get("stage_index", 0)
    total = info.get("total_stages", 0)
    day = info.get("day_in_stage", 0)
    dur = info.get("stage_duration", 0)
    progress = info.get("progress_pct", 0)
    next_s = info.get("next_stage", "")

    bar_len = 10
    filled = max(1, round(progress / 100 * bar_len))
    bar = "█" * filled + "░" * (bar_len - filled)

    risks = get_stage_specific_risks(crop, stage, "en")

    lines = [
        f"🌱 *Weekly Crop Intelligence — {crop}*",
        "",
        f"📌 *Current Stage:* {stage} (Stage {idx}/{total})",
        f"📅 Day {day + 1} of {dur} in this stage",
        f"📊 Overall progress: [{bar}] {progress}%",
    ]

    if next_s:
        lines.append(f"➡️ *Next stage:* {next_s}")

    if risks:
        lines.append("")
        lines.append("⚠️ *Stage-Specific Risks:*")
        for r in risks:
            lines.append(f"  • {r}")

    lines.append("")
    lines.append(
        "ℹ️ _This estimate is based on your registration date. "
        "Actual stage may vary by variety and conditions._"
    )

    return "\n".join(lines)


def _build_stage_report_kn(info: dict) -> str:
    crop = info.get("crop_type", "ಬೆಳೆ")
    stage = info.get("stage_name", "Unknown")
    idx = info.get("stage_index", 0)
    total = info.get("total_stages", 0)
    day = info.get("day_in_stage", 0)
    dur = info.get("stage_duration", 0)
    progress = info.get("progress_pct", 0)
    next_s = info.get("next_stage", "")

    bar_len = 10
    filled = max(1, round(progress / 100 * bar_len))
    bar = "█" * filled + "░" * (bar_len - filled)

    risks = get_stage_specific_risks(crop, stage, "kn")

    lines = [
        f"🌱 *ಸಾಪ್ತಾಹಿಕ ಬೆಳೆ ಬುದ್ಧಿಮತ್ತೆ — {crop}*",
        "",
        f"📌 *ಪ್ರಸ್ತುತ ಹಂತ:* {stage} (ಹಂತ {idx}/{total})",
        f"📅 ಈ ಹಂತದಲ್ಲಿ {dur} ದಿನಗಳಲ್ಲಿ ದಿನ {day + 1}",
        f"📊 ಒಟ್ಟಾರೆ ಪ್ರಗತಿ: [{bar}] {progress}%",
    ]

    if next_s:
        lines.append(f"➡️ *ಮುಂದಿನ ಹಂತ:* {next_s}")

    if risks:
        lines.append("")
        lines.append("⚠️ *ಹಂತ-ನಿರ್ದಿಷ್ಟ ಅಪಾಯಗಳು:*")
        for r in risks:
            lines.append(f"  • {r}")

    lines.append("")
    lines.append(
        "ℹ️ _ಈ ಅಂದಾಜು ನಿಮ್ಮ ನೋಂದಣಿ ದಿನಾಂಕದ ಆಧಾರಿತ. "
        "ನಿಜವಾದ ಹಂತ ತಳಿ ಮತ್ತು ಪರಿಸ್ಥಿತಿಗಳ ಪ್ರಕಾರ ಬದಲಾಗಬಹುದು._"
    )

    return "\n".join(lines)


# Supported crop list (for bot selection menus)
SUPPORTED_CROPS = list(CROP_STAGES.keys())
