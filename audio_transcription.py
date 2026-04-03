"""
audio_transcription.py - Audio transcription via Google Gemini API.

We use Gemini 1.5 Flash or higher models which natively support audio.
"""

from dotenv import load_dotenv
load_dotenv()

import os
from pathlib import Path

def _get_best_gemini_audio_model(genai) -> str:
    """Try preferred models in order; fall back to first available generateContent model."""
    preferred = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-preview-04-17",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
    ]
    try:
        available = {m.name.replace("models/", "") for m in genai.list_models()
                     if "generateContent" in m.supported_generation_methods}
        for name in preferred:
            if name in available:
                print(f"[audio] Using Gemini model: {name}")
                return name
        fallback = next(iter(available), None)
        if fallback:
            print(f"[audio] Using fallback Gemini model: {fallback}")
            return fallback
    except Exception as e:
        print(f"[audio] Could not list models ({e}), trying gemini-2.0-flash")
    return "gemini-2.0-flash"

def transcribe_audio_file(audio_path: str, language: str = "en") -> str:
    """
    Transcribe the given OGG audio file using Gemini.
    """
    import google.generativeai as genai
    
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Cannot transcribe audio.")

    genai.configure(api_key=api_key)
    model_name = _get_best_gemini_audio_model(genai)
    model = genai.GenerativeModel(model_name)
    
    # Read the audio bytes
    audio_bytes = Path(audio_path).read_bytes()
    
    # Determine transcription prompt based on language
    if language == "kn":
        prompt = "Transcribe this audio. It may be in Kannada or English. Return ONLY the transcribed text and nothing else."
    else:
        prompt = "Transcribe this audio. It is mostly in English. Return ONLY the transcribed text and nothing else."
        
    part = {
        "mime_type": "audio/ogg",
        "data": audio_bytes
    }
    
    response = model.generate_content([prompt, part])
    
    text = response.text.strip()
    return text
