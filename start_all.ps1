# ─────────────────────────────────────────────────────────────────────────────
# CropRadar — Start All Services
# ─────────────────────────────────────────────────────────────────────────────
# Opens 4 separate terminal windows:
#   1. FastAPI backend     (port 8000)
#   2. Telegram bot        (long-polling, no tunnel needed)
#   3. WhatsApp bot        (port 5001 — needs a tunnel)
#   4. Admin dashboard     (Streamlit, port 8501)
#
# Then starts cloudflared tunnel for WhatsApp webhook and prints the URL.
#
# Usage:
#   cd D:\Z-work\CropRadar\CropRadar-01
#   .\start_all.ps1
# ─────────────────────────────────────────────────────────────────────────────

$PY    = "C:\Users\USER\AppData\Local\Programs\Python\Python311\python.exe"
$ROOT  = $PSScriptRoot          # folder where this script lives
$TITLE_COLOR = "Cyan"

function Write-Header {
    param([string]$msg)
    Write-Host ""
    Write-Host "  $msg" -ForegroundColor $TITLE_COLOR
    Write-Host ""
}

# ── Sanity checks ─────────────────────────────────────────────────────────────
if (-not (Test-Path $PY)) {
    Write-Host "ERROR: Python 3.11 not found at $PY" -ForegroundColor Red
    Write-Host "Edit the `$PY variable at the top of start_all.ps1"
    exit 1
}

if (-not (Test-Path "$ROOT\.env")) {
    Write-Host "WARNING: .env file not found — services may fail to start." -ForegroundColor Yellow
}

Write-Header "🌾 CropRadar — Starting All Services"

# ── 1. FastAPI backend ────────────────────────────────────────────────────────
Write-Host "  [1/4] Launching FastAPI backend (port 8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$ROOT'; Write-Host '── FastAPI Backend ──' -ForegroundColor Green; & '$PY' -m uvicorn api:app --reload --host 0.0.0.0 --port 8000"
) -WindowStyle Normal

Start-Sleep -Seconds 2   # give API a head-start before bots connect

# ── 2. Telegram bot ───────────────────────────────────────────────────────────
Write-Host "  [2/4] Launching Telegram bot..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$ROOT'; Write-Host '── Telegram Bot ──' -ForegroundColor Blue; & '$PY' bot.py"
) -WindowStyle Normal

# ── 3. WhatsApp bot ───────────────────────────────────────────────────────────
Write-Host "  [3/4] Launching WhatsApp bot (port 5001)..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$ROOT'; Write-Host '── WhatsApp Bot ──' -ForegroundColor Magenta; & '$PY' whatsapp_bot.py"
) -WindowStyle Normal

# ── 4. Admin dashboard ────────────────────────────────────────────────────────
Write-Host "  [4/4] Launching Admin Dashboard (port 8501)..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$ROOT'; Write-Host '── Admin Dashboard ──' -ForegroundColor Yellow; & '$PY' -m streamlit run admin_dashboard.py --server.port 8501 --server.headless true"
) -WindowStyle Normal

Start-Sleep -Seconds 3   # wait for WhatsApp bot to be up before tunnelling

# ── Cloudflared tunnel for WhatsApp webhook ────────────────────────────────────
Write-Host ""
Write-Host "  Checking for cloudflared..." -ForegroundColor Cyan

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue

if ($cloudflared) {
    Write-Host "  Starting cloudflared tunnels → :8000 (API) and :5001 (WhatsApp)" -ForegroundColor Cyan
    Write-Host ""

    $tunnelJobApi = Start-Job -ScriptBlock { & cloudflared tunnel --url http://localhost:8000 2>&1 }
    $tunnelJobWa  = Start-Job -ScriptBlock { & cloudflared tunnel --url http://localhost:5001 2>&1 }

    $apiUrl    = $null
    $tunnelUrl = $null
    $attempts  = 0
    while ((-not $tunnelUrl -or -not $apiUrl) -and $attempts -lt 40) {
        Start-Sleep -Milliseconds 500
        if (-not $apiUrl) {
            foreach ($line in (Receive-Job $tunnelJobApi)) {
                if ($line -match "https://[a-z0-9\-]+\.trycloudflare\.com") { $apiUrl = $matches[0]; break }
            }
        }
        if (-not $tunnelUrl) {
            foreach ($line in (Receive-Job $tunnelJobWa)) {
                if ($line -match "https://[a-z0-9\-]+\.trycloudflare\.com") { $tunnelUrl = $matches[0]; break }
            }
        }
        $attempts++
    }

    if ($tunnelUrl) { $webhookUrl = "$tunnelUrl/whatsapp" }

    Write-Host ""
    Write-Host "  ┌─────────────────────────────────────────────────────┐" -ForegroundColor Green
    Write-Host "  │  ✅ Tunnels are live!                                │" -ForegroundColor Green
    Write-Host "  │                                                      │" -ForegroundColor Green
    if ($apiUrl) {
    Write-Host "  │  📱 App Backend URL (paste into app ⚙️ Settings):    │" -ForegroundColor Green
    Write-Host "  │  $apiUrl" -ForegroundColor Cyan
    Write-Host "  │                                                      │" -ForegroundColor Green
    }
    Write-Host "  │  💬 WhatsApp Webhook (paste into Twilio):            │" -ForegroundColor Green
    Write-Host "  │  $webhookUrl" -ForegroundColor Yellow
    Write-Host "  │                                                      │" -ForegroundColor Green
    Write-Host "  │  Paste webhook → Twilio → 'When a message comes in' │" -ForegroundColor Green
    Write-Host "  └─────────────────────────────────────────────────────┘" -ForegroundColor Green
} else {
    Write-Host "  cloudflared not found — skipping tunnel." -ForegroundColor Yellow
    Write-Host "  Start it manually:  cloudflared tunnel --url http://localhost:5001" -ForegroundColor Gray
}

# ── Summary ───────────────────────────────────────────────────────────────────
$divider = "  " + ("─" * 57)

Write-Host ""
Write-Host $divider -ForegroundColor DarkCyan
Write-Host "  🌾  CropRadar — All Services Running" -ForegroundColor Cyan
Write-Host $divider -ForegroundColor DarkCyan
Write-Host ""
Write-Host "  🔧  FastAPI backend" -ForegroundColor White
Write-Host "      http://localhost:8000"       -ForegroundColor Green
Write-Host "      http://localhost:8000/docs   ← interactive API docs" -ForegroundColor DarkGreen
Write-Host ""
Write-Host "  🖥️   Admin Dashboard" -ForegroundColor White
Write-Host "      http://localhost:8501        ← open in browser" -ForegroundColor Green
Write-Host "      Login: admin / cropradar123" -ForegroundColor DarkGreen
Write-Host ""
Write-Host "  📱  App Backend URL (paste into app ⚙️ API Settings)
if ($apiUrl) {
    Write-Host "      $apiUrl" -ForegroundColor Cyan
} else {
    Write-Host "      (not detected — check cloudflared output)" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  💬  WhatsApp Webhook (paste into Twilio)" -ForegroundColor White" -ForegroundColor White
if ($tunnelUrl) {
    Write-Host "      $webhookUrl" -ForegroundColor Yellow
} else {
    Write-Host "      (tunnel URL not detected — check cloudflared output)" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  🤖  Telegram Bot" -ForegroundColor White
Write-Host "      Running via long-polling — no URL needed" -ForegroundColor DarkGreen
Write-Host ""
Write-Host "  ⏰  Proactive Scheduler" -ForegroundColor White
Write-Host "      Daily risk alerts:  7:00 AM IST" -ForegroundColor DarkGreen
Write-Host "      Weekly crop stage:  Monday 8:00 AM IST" -ForegroundColor DarkGreen
Write-Host "      Outbreak scan:      Every 6 hours" -ForegroundColor DarkGreen
Write-Host ""
Write-Host $divider -ForegroundColor DarkCyan
Write-Host "  Press Ctrl+C to stop the tunnel." -ForegroundColor DarkGray
Write-Host "  Close individual windows to stop each service." -ForegroundColor DarkGray
Write-Host $divider -ForegroundColor DarkCyan
Write-Host ""

# Keep this window open (tunnel jobs run here)
if ($cloudflared) {
    if ($tunnelJobApi) { Wait-Job $tunnelJobApi | Out-Null }
    if ($tunnelJobWa)  { Wait-Job $tunnelJobWa  | Out-Null }
}
