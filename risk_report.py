"""
risk_report.py - Telegram-friendly crop risk report formatter for CropRadar.

Converts structured risk analysis output into bilingual Telegram messages
that are clearly distinct from outbreak alerts.
"""


def build_crop_risk_report(language: str, risk_result: dict) -> str:
    """
    Build a Telegram-formatted risk report message.

    Args:
        language: 'en' or 'kn'
        risk_result: dict from risk_model.score_area_risk()

    Returns:
        Formatted string ready for Telegram (Markdown parse mode)
    """
    if language == "kn":
        return _build_kannada_report(risk_result)
    return _build_english_report(risk_result)


# ---------------------------------------------------------------------------
# Risk level emoji mapping
# ---------------------------------------------------------------------------

def _risk_emoji(level: str) -> str:
    return {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(level, "⚪")


# ---------------------------------------------------------------------------
# English report
# ---------------------------------------------------------------------------

def _build_english_report(r: dict) -> str:
    level = r.get("risk_level", "Unknown")
    score = r.get("risk_score", 0)
    emoji = _risk_emoji(level)

    crops = r.get("likely_crops_at_risk", [])
    diseases = r.get("likely_diseases", [])
    reasons = r.get("reasons", [])
    recs = r.get("recommendations", [])

    lines = [
        "🔮 *Crop Risk Report for Your Area*",
        "",
        f"{emoji} *Risk Level:* {level} ({score}/100)",
    ]

    if crops:
        lines.append(f"🌱 *Crops at Risk:* {', '.join(crops)}")

    if diseases:
        lines.append(f"🦠 *Possible Diseases:* {', '.join(diseases)}")

    if reasons:
        lines.append("")
        lines.append("📋 *Why this area is at risk:*")
        for reason in reasons[:5]:
            lines.append(f"  • {reason}")

    if recs:
        lines.append("")
        lines.append("🛡️ *Recommended Actions:*")
        for rec in recs[:5]:
            lines.append(f"  • {rec}")

    lines.append("")
    lines.append(
        "ℹ️ _This is a preventive early warning based on weather, "
        "vegetation, and regional data — not a confirmed outbreak._"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Kannada report
# ---------------------------------------------------------------------------

def _build_kannada_report(r: dict) -> str:
    level = r.get("risk_level", "Unknown")
    score = r.get("risk_score", 0)
    emoji = _risk_emoji(level)

    level_kn = {"Low": "ಕಡಿಮೆ", "Medium": "ಮಧ್ಯಮ", "High": "ಹೆಚ್ಚು"}.get(level, level)

    crops = r.get("likely_crops_at_risk", [])
    diseases = r.get("likely_diseases", [])
    reasons = r.get("reasons", [])
    recs = r.get("recommendations", [])

    lines = [
        "🔮 *ನಿಮ್ಮ ಪ್ರದೇಶದ ಬೆಳೆ ಅಪಾಯ ವರದಿ*",
        "",
        f"{emoji} *ಅಪಾಯ ಮಟ್ಟ:* {level_kn} ({score}/100)",
    ]

    if crops:
        lines.append(f"🌱 *ಅಪಾಯದಲ್ಲಿರುವ ಬೆಳೆಗಳು:* {', '.join(crops)}")

    if diseases:
        lines.append(f"🦠 *ಸಂಭಾವ್ಯ ರೋಗಗಳು:* {', '.join(diseases)}")

    if reasons:
        lines.append("")
        lines.append("📋 *ಈ ಪ್ರದೇಶ ಏಕೆ ಅಪಾಯದಲ್ಲಿದೆ:*")
        for reason in reasons[:5]:
            lines.append(f"  • {reason}")

    if recs:
        lines.append("")
        lines.append("🛡️ *ಶಿಫಾರಸು ಮಾಡಿದ ಕ್ರಮಗಳು:*")
        for rec in recs[:5]:
            lines.append(f"  • {rec}")

    lines.append("")
    lines.append(
        "ℹ️ _ಇದು ಹವಾಮಾನ, ಸಸ್ಯ ಆರೋಗ್ಯ ಮತ್ತು ಪ್ರಾದೇಶಿಕ ಮಾಹಿತಿ ಆಧಾರಿತ "
        "ಮುಂಜಾಗ್ರತಾ ಎಚ್ಚರಿಕೆ — ದೃಢೀಕರಿಸಿದ ರೋಗ ಹರಡುವಿಕೆ ಅಲ್ಲ._"
    )

    return "\n".join(lines)
