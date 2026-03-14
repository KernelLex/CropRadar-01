"""
vision_diagnosis.py - Crop disease analysis via Google Gemini Vision API.

Set the environment variable GEMINI_API_KEY (or OPENAI_API_KEY if you
switch to OpenAI) before running the server.

Falls back to a mock response when no key is configured so the prototype
can be demoed without an API account.
"""

# Load .env before reading env vars
from dotenv import load_dotenv
load_dotenv()

import base64
import json
import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def build_prompt(language: str = "en") -> str:
    """
    Build the Gemini prompt with a language instruction.
    language: 'en' for English, 'kn' for Kannada.
    """
    if language == "kn":
        lang_instruction = (
            "IMPORTANT: Write the values for 'remedy' and 'prevention' in Kannada (ಕನ್ನಡ) script. "
            "Write 'disease_name' in English followed by the Kannada name in parentheses if known. "
            "Keep 'confidence' as one of: High, Medium, Low (in English)."
        )
    else:
        lang_instruction = (
            "Write all values in English."
        )

    return f"""
You are an expert agronomist and plant pathologist.
Analyze the leaf image provided and identify any crop disease present.

{lang_instruction}

Return ONLY a valid JSON object with exactly these keys (no extra text, no markdown):
{{
  "disease_name": "<name of disease or 'Healthy Leaf' if no disease>",
  "confidence": "<High | Medium | Low>",
  "remedy": "<brief actionable remedy in 2-3 sentences>",
  "prevention": "<brief preventive measures in 2-3 sentences>"
}}

Common diseases to consider: Leaf Blight, Powdery Mildew, Leaf Spot, Rust, Healthy Leaf.
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_from_text(text: str) -> dict:
    """
    Extract the first complete JSON object found in *text*.
    Uses a stack-based approach to handle nested braces correctly.
    """
    # First, strip markdown code fences if the model wrapped it
    text = re.sub(r"```(?:json)?", "", text).strip()

    # Find the first '{' and match its closing '}'
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in model response: {text!r}")

    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"Found JSON-like block but could not parse it: {candidate!r}"
                    ) from e

    raise ValueError(f"Unmatched braces in model response: {text!r}")


# ---------------------------------------------------------------------------
# Gemini Vision (primary)
# ---------------------------------------------------------------------------

def _get_best_gemini_model(genai) -> str:
    """Try preferred models in order; fall back to first available generateContent model."""
    preferred = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-preview-04-17",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
        "gemini-pro-vision",
    ]
    try:
        available = {m.name.replace("models/", "") for m in genai.list_models()
                     if "generateContent" in m.supported_generation_methods}
        for name in preferred:
            if name in available:
                print(f"[vision] Using Gemini model: {name}")
                return name
        # Last resort: pick any available model
        fallback = next(iter(available), None)
        if fallback:
            print(f"[vision] Using fallback Gemini model: {fallback}")
            return fallback
    except Exception as e:
        print(f"[vision] Could not list models ({e}), trying gemini-2.0-flash")
    return "gemini-2.0-flash"


def _analyze_with_gemini(image_path: str, language: str = "en") -> dict:
    """Call Google Gemini Vision API using PIL Image (most reliable method)."""
    import google.generativeai as genai
    from PIL import Image

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    genai.configure(api_key=api_key)
    model_name = _get_best_gemini_model(genai)
    model = genai.GenerativeModel(model_name)

    # PIL Image is the most reliable way to pass images to the Gemini SDK
    img = Image.open(image_path)

    response = model.generate_content([build_prompt(language), img])
    return _parse_json_from_text(response.text)



# ---------------------------------------------------------------------------
# OpenAI Vision (alternative - swap in if you prefer GPT-4o)
# ---------------------------------------------------------------------------

def _analyze_with_openai(image_path: str, language: str = "en") -> dict:
    """Call OpenAI GPT-4o Vision API. Requires OPENAI_API_KEY."""
    import openai

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = openai.OpenAI(api_key=api_key)
    b64 = base64.b64encode(Path(image_path).read_bytes()).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": build_prompt(language)},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                ],
            }
        ],
        max_tokens=512,
    )
    return _parse_json_from_text(response.choices[0].message.content)


# ---------------------------------------------------------------------------
# Mock (no API key)
# ---------------------------------------------------------------------------

def _analyze_mock(image_path: str) -> dict:
    """Return a deterministic mock response for demo/testing."""
    import hashlib

    diseases = [
        {
            "disease_name": "Leaf Blight",
            "confidence": "High",
            "remedy": "Remove and destroy infected leaves immediately. Apply copper-based fungicides every 7 days.",
            "prevention": "Ensure good air circulation. Avoid overhead watering. Use disease-resistant varieties.",
        },
        {
            "disease_name": "Powdery Mildew",
            "confidence": "Medium",
            "remedy": "Spray with a solution of baking soda (1 tsp per litre) or apply neem oil. Repeat weekly.",
            "prevention": "Plant in full sun. Avoid excess nitrogen fertiliser. Water at the base of plants.",
        },
        {
            "disease_name": "Leaf Spot",
            "confidence": "High",
            "remedy": "Apply chlorothalonil-based fungicide. Remove heavily infected foliage.",
            "prevention": "Rotate crops annually. Use certified disease-free seeds. Maintain healthy soil.",
        },
        {
            "disease_name": "Rust",
            "confidence": "Medium",
            "remedy": "Apply propiconazole or tebuconazole fungicide. Improve drainage around plants.",
            "prevention": "Use rust-resistant cultivars. Destroy crop debris after harvest.",
        },
        {
            "disease_name": "Healthy Leaf",
            "confidence": "High",
            "remedy": "No treatment required. Continue regular monitoring.",
            "prevention": "Maintain balanced nutrition and adequate irrigation.",
        },
    ]

    digest = int(hashlib.md5(Path(image_path).read_bytes()).hexdigest(), 16)
    return diseases[digest % len(diseases)]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_crop_image(image_path: str, language: str = "en") -> dict:
    """
    Analyze a crop leaf image and return a diagnosis dict.
    language: 'en' for English, 'kn' for Kannada — controls the AI response language.
    """
    import time

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    openai_key  = os.environ.get("OPENAI_API_KEY", "").strip()

    if gemini_key:
        print(f"[vision] Using Gemini Vision (key: ...{gemini_key[-6:]})")
        # Retry up to 3 times on 429 quota errors
        for attempt in range(1, 4):
            try:
                return _analyze_with_gemini(image_path, language=language)
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                    if attempt < 3:
                        wait = 5 * attempt  # 5s, 10s back-off
                        print(f"[vision] Gemini 429 quota hit, retrying in {wait}s (attempt {attempt}/3)…")
                        time.sleep(wait)
                        continue
                    # All retries exhausted — fall back to mock so the bot still replies
                    print("[vision] Gemini quota exhausted after 3 attempts — using mock response.")
                    return _analyze_mock(image_path)
                # Non-quota error — re-raise immediately
                raise

    if openai_key:
        print("[vision] Using OpenAI Vision")
        return _analyze_with_openai(image_path, language=language)

    print("[vision] WARNING: No API key found – using mock response.")
    return _analyze_mock(image_path)

