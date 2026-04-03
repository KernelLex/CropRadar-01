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
    "cd '$ROOT'; Write-Host '── FastAPI Backend ──' -ForegroundColor Green; & '$PY' -m uvicorn api:app --reload --port 8000"
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
    Write-Host "  Starting cloudflared tunnel → http://localhost:5001" -ForegroundColor Cyan
    Write-Host ""

    # Run cloudflared in this window so we can read the URL
    $tunnelJob = Start-Job -ScriptBlock {
        & cloudflared tunnel --url http://localhost:5001 2>&1
    }

    # Wait up to 12s for the tunnel URL to appear
    $tunnelUrl = $null
    $attempts  = 0
    while (-not $tunnelUrl -and $attempts -lt 24) {
        Start-Sleep -Milliseconds 500
        $output = Receive-Job $tunnelJob
        foreach ($line in $output) {
            if ($line -match "https://[a-z0-9\-]+\.trycloudflare\.com") {
                $tunnelUrl = $matches[0]
                break
            }
        }
        $attempts++
    }

    if ($tunnelUrl) {
        $webhookUrl = "$tunnelUrl/whatsapp"
        Write-Host ""
        Write-Host "  ┌─────────────────────────────────────────────────────┐" -ForegroundColor Green
        Write-Host "  │  ✅ Tunnel is live!                                  │" -ForegroundColor Green
        Write-Host "  │                                                      │" -ForegroundColor Green
        Write-Host "  │  WhatsApp Webhook URL:                               │" -ForegroundColor Green
        Write-Host "  │  $webhookUrl" -ForegroundColor Yellow
        Write-Host "  │                                                      │" -ForegroundColor Green
        Write-Host "  │  Paste this into Twilio sandbox settings             │" -ForegroundColor Green
        Write-Host "  │  → 'When a message comes in'                        │" -ForegroundColor Green
        Write-Host "  └─────────────────────────────────────────────────────┘" -ForegroundColor Green
    } else {
        Write-Host "  Tunnel started but URL not detected yet." -ForegroundColor Yellow
        Write-Host "  Check the cloudflared output for the https:// URL."
    }
} else {
    Write-Host "  cloudflared not found — skipping tunnel." -ForegroundColor Yellow
    Write-Host "  Start it manually:  cloudflared tunnel --url http://localhost:5001" -ForegroundColor Gray
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ─────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Service               URL" -ForegroundColor DarkGray
Write-Host "  ─────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  FastAPI backend     → http://localhost:8000/docs"
Write-Host "  Admin dashboard     → http://localhost:8501"
Write-Host "  WhatsApp webhook    → (tunnel URL above)/whatsapp"
Write-Host "  Telegram bot        → polling (no URL needed)"
Write-Host "  ─────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Press Ctrl+C here to stop the tunnel." -ForegroundColor DarkGray
Write-Host "  Close individual windows to stop each service." -ForegroundColor DarkGray
Write-Host ""

# Keep this window open (tunnel job runs here)
if ($cloudflared) {
    Wait-Job $tunnelJob | Out-Null
}
