# CropRadar: Project Architecture & Technical Summary

## 1. Overview
**CropRadar** is an AI-powered agricultural assist platform designed to bring expert agronomy directly to farmers via familiar messaging channels (Telegram and WhatsApp). Farmers can send images of infected crop leaves or record audio notes in their native language (English or Kannada). The system diagnoses diseases using advanced multimodal AI (Google Gemini), alerts users of immediate nearby outbreak risks, and visualizes disease intelligence locally.

---

## 2. System Components
The source code is modularized into distinct domains:

### **Bot Gateways (The Frontend)**
*   `whatsapp_bot.py`: A long-polling Flask app functioning as a webhook for the Meta WhatsApp Cloud API. It maintains conversational state in-memory and processes text, geolocation attachments, photos, and voice notes (`.ogg`).
*   `bot.py`: The Telegram equivalent using `python-telegram-bot` maintaining the exact same pipeline but interacting via Long Polling directly with Telegram servers.

### **The Backend Core**
*   `api.py`: A `FastAPI` instance acting as the bridge between bots, AI, and the database. It exposes endpoints (`/analyze-image`, `/transcribe-audio`, `/nearby-alerts`, `/reports`) enabling secure inter-service communication locally or remotely.

### **AI Modules**
*   `vision_diagnosis.py`: Wraps standard image attachments logic through the Google Gemini Vision API `gemini-1.5-flash` or `gemini-2.0-flash`. The AI evaluates the image against an internal prompt enforcing strict structured JSON outputs dictating (Disease, Confidence, Remedy, Prevention). Includes fallback to mock results if API limits are reached.
*   `audio_transcription.py`: Converts raw `.ogg` voice notes into strings by tunneling the audio bitstream straight into Gemini's multi-modal processing queue. 

### **Data & Visualisation Layer**
*   `database.py`: The SQLite storage engine (`cropradar.db`). It records disease types, metadata, timestamps, and geospatial coordinates. Includes mathematical Great-circle (`_haversine_km`) logic.
*   `map_dashboard.py`: A Streamlit dashboard visualizing the SQLite footprint on interactive geographical maps via Folium. 

---

## 3. The Pipeline Execution (Step-by-Step)

1.  **Session Initiation**: User sends a generic "hi" establishing a new conversational state (`WAITING_LANGUAGE`). 
2.  **Language Check**: User replies 1 for English or 2 for Kannada. (Voice notes mapped to numbers work too).
3.  **Geo-Fencing Risk Engine**: 
    * User shares GPS coordinates (`WAITING_LOCATION`).
    * The Gateway requests `GET /nearby-alerts` from the backend API.
    * `database.py` calculates the Haversine distance between the user's location and all recent active reports.
    * If 3 or more of a *single disease type* exist inside a 50 KM radius within the last 48 hours, an immediate Outbreak Warning is sent to the user.
4.  **Audio / Visual Input (`WAITING_PHOTO`)**:
    * User sends an image or a microphone voice command.
    * **Audio**: Re-routes via `POST /transcribe-audio`. Decodes to text internally.
    * **Photo**: Saved temporarily on disk, pushed via `POST /analyze-image`. 
5.  **AI Invocation**: Gemini parses the image/audio, producing either translated agricultural advice or command text formats.
6.  **Resolution & Storage**: 
    * Result sets are persisted via `insert_report` updating the global threat map.
    * Formatted diagnostic blocks (with appropriate emojis based on threat confidence) are dispatched to the messaging bot payload.

---

## 4. Possible Faults & Limitations

While the pipeline is robust, it faces the following architectural risks:

### A. Environmental / Noise Vulnerabilities
*   **Audio Ambiguity**: Severe farm environments (wind or tractor mechanical noise) or very heavy rural accents may cause audio models to return empty strings. **Mitigation added**: *Built-in retry loop mapping up to 3 failed occurrences before prompting a forced text-fallback mechanism.*
*   **AI Hallucination**: AI might diagnose healthy leaf shadows as "Blight." **Mitigation added**: *The `confidence` output string prevents farmers from deploying severe chemical remedies based on "Low" diagnostic intelligence.*

### B. Scalability Hardware Locks
*   **Disk-Locked SQLite**: `database.py` leverages `cropradar.db` in the local path root. If the repository is deployed on a Serverless function architecture (like Vercel or AWS Lambda), SQLite states are ephemeral and will reset to zero entirely upon spin-down. For cloud deployments, migration to PostgreSQL/Supabase is required.
*   **In-Memory Session States**: The WhatsApp Flask server maintains conversational routing (`sessions: dict`) locally. A multi-instance architecture deployment (e.g. Docker swarm) will lose session continuity across load balancers out-of-the-box. 

### C. Resource Spikes
*   **Webhooks Expirations**: Meta WhatsApp Webhook expects an `HTTP 200` instantaneously. If Image generation processing through Gemini's API takes longer than Meta's timeout, Meta will retry the queued HTTP request repeatedly, accidentally triggering multiple overlapping bot events for the same message.
*   **Rate Limits**: Free Gemini API (`GEMINI_API_KEY`) hits error 429 swiftly. **Mitigation added**: *A 3-turn retry mechanism triggers Exponential Back-Off. Mock deterministic responses trigger upon total exhaustion to prevent UI hanging.*
