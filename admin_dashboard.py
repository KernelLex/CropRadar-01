"""
admin_dashboard.py — CropRadar Admin Panel (Streamlit)

Run:
    streamlit run admin_dashboard.py --server.port 8501

Login:
    Username : admin
    Password : set ADMIN_PASSWORD in .env  (default: cropradar123)
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DB_PATH        = "cropradar.db"
PHOTOS_DIR     = Path("photos")
ADMIN_USER     = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "cropradar123")

st.set_page_config(
    page_title="CropRadar Admin",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    try:
        with get_conn() as conn:
            return pd.read_sql_query(sql, conn, params=params)
    except Exception as e:
        st.error(f"DB error: {e}")
        return pd.DataFrame()


def execute(sql: str, params: tuple = ()) -> None:
    with get_conn() as conn:
        conn.execute(sql, params)
        conn.commit()


def fmt_ts(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%d %b %Y  %H:%M")
    except Exception:
        return ts or "—"


CONF_COLOR = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
RISK_COLOR = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}

# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────

def login_page():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.image("https://img.icons8.com/color/96/000000/plant-under-sun.png", width=72)
        st.markdown("## 🌾 CropRadar Admin")
        st.markdown("---")
        username = st.text_input("Username", placeholder="admin")
        password = st.text_input("Password", type="password", placeholder="••••••••")
        if st.button("Login", use_container_width=True, type="primary"):
            if username == ADMIN_USER and password == ADMIN_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Invalid credentials")


if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    login_page()
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🌾 CropRadar Admin")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["📊 Overview", "🦠 Disease Reports", "👥 Bot Users",
         "⚠️ Outbreak Alerts", "🌤️ Weather Cache",
         "🛰️ NDVI Snapshots", "📈 Risk Scores"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()
    st.caption(f"DB: `{DB_PATH}`")
    if Path(DB_PATH).exists():
        size_kb = Path(DB_PATH).stat().st_size / 1024
        st.caption(f"Size: {size_kb:.1f} KB")

# ─────────────────────────────────────────────────────────────────────────────
# Overview
# ─────────────────────────────────────────────────────────────────────────────

if page == "📊 Overview":
    st.title("📊 Dashboard Overview")

    reports_df  = query("SELECT * FROM disease_reports ORDER BY timestamp DESC")
    users_df    = query("SELECT * FROM bot_users")
    alerts_df   = query("SELECT * FROM outbreak_notifications ORDER BY triggered_at DESC")
    risk_df     = query("SELECT * FROM risk_scores ORDER BY created_at DESC")

    # KPI row
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("📋 Total Reports",    len(reports_df))
    col2.metric("👥 Bot Users",        len(users_df))
    col3.metric("⚠️ Outbreak Alerts",  len(alerts_df))
    col4.metric("📈 Risk Assessments", len(risk_df))

    if not reports_df.empty:
        cutoff = (datetime.utcnow() - timedelta(hours=48)).isoformat()
        recent = reports_df[reports_df["timestamp"] >= cutoff]
        col5.metric("🕐 Reports (48h)", len(recent))
    else:
        col5.metric("🕐 Reports (48h)", 0)

    st.markdown("---")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("🦠 Disease Distribution")
        if not reports_df.empty:
            dist = reports_df["disease_type"].value_counts().reset_index()
            dist.columns = ["Disease", "Count"]
            st.bar_chart(dist.set_index("Disease"))
        else:
            st.info("No reports yet.")

    with col_right:
        st.subheader("📅 Reports Over Time")
        if not reports_df.empty:
            reports_df["date"] = pd.to_datetime(
                reports_df["timestamp"], errors="coerce"
            ).dt.date
            timeline = reports_df.groupby("date").size().reset_index(name="Count")
            st.line_chart(timeline.set_index("date"))
        else:
            st.info("No reports yet.")

    st.markdown("---")
    st.subheader("🕐 5 Most Recent Reports")
    if not reports_df.empty:
        recent5 = reports_df.head(5)[
            ["id", "disease_type", "confidence", "latitude", "longitude", "timestamp"]
        ].copy()
        recent5["timestamp"] = recent5["timestamp"].apply(fmt_ts)
        recent5["confidence"] = recent5["confidence"].apply(
            lambda c: f"{CONF_COLOR.get(c, '⚪')} {c}" if c else "—"
        )
        st.dataframe(recent5, use_container_width=True, hide_index=True)
    else:
        st.info("No reports yet.")

    if not users_df.empty:
        st.markdown("---")
        st.subheader("👥 Active Bot Users by Language")
        lang_dist = users_df["language"].value_counts().reset_index()
        lang_dist.columns = ["Language", "Count"]
        st.bar_chart(lang_dist.set_index("Language"))

# ─────────────────────────────────────────────────────────────────────────────
# Disease Reports
# ─────────────────────────────────────────────────────────────────────────────

elif page == "🦠 Disease Reports":
    st.title("🦠 Disease Reports")

    df = query("SELECT * FROM disease_reports ORDER BY timestamp DESC")

    if df.empty:
        st.info("No disease reports in the database.")
        st.stop()

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        diseases = ["All"] + sorted(df["disease_type"].dropna().unique().tolist())
        sel_disease = st.selectbox("Filter by Disease", diseases)
    with col2:
        confs = ["All"] + sorted(df["confidence"].dropna().unique().tolist())
        sel_conf = st.selectbox("Filter by Confidence", confs)
    with col3:
        has_loc = st.selectbox("Location", ["All", "With GPS", "Without GPS"])

    filtered = df.copy()
    if sel_disease != "All":
        filtered = filtered[filtered["disease_type"] == sel_disease]
    if sel_conf != "All":
        filtered = filtered[filtered["confidence"] == sel_conf]
    if has_loc == "With GPS":
        filtered = filtered[filtered["latitude"].notna()]
    elif has_loc == "Without GPS":
        filtered = filtered[filtered["latitude"].isna()]

    st.caption(f"Showing {len(filtered)} of {len(df)} records")
    st.markdown("---")

    # Card-style display for records with photos; table for the rest
    has_photos = filtered["photo_path"].notna() & (filtered["photo_path"] != "")

    if has_photos.any():
        st.subheader("📸 Reports with Photos")
        photo_rows = filtered[has_photos].head(20)
        cols = st.columns(3)
        for i, (_, row) in enumerate(photo_rows.iterrows()):
            with cols[i % 3]:
                photo_file = Path(str(row["photo_path"])).name
                photo_path = PHOTOS_DIR / photo_file
                if photo_path.exists():
                    st.image(str(photo_path), use_container_width=True)
                conf_icon = CONF_COLOR.get(row.get("confidence"), "⚪")
                st.markdown(
                    f"**{row['disease_type']}** {conf_icon}  \n"
                    f"🕐 {fmt_ts(row['timestamp'])}  \n"
                    f"📍 {row['latitude']:.4f}°, {row['longitude']:.4f}°"
                    if pd.notna(row.get("latitude"))
                    else f"**{row['disease_type']}** {conf_icon}  \n"
                         f"🕐 {fmt_ts(row['timestamp'])}  \n📍 No location"
                )
                if st.button(f"🗑️ Delete #{row['id']}", key=f"del_rep_{row['id']}"):
                    execute("DELETE FROM disease_reports WHERE id = ?", (int(row["id"]),))
                    st.success(f"Deleted report #{row['id']}")
                    st.rerun()
                st.markdown("---")

    st.subheader("📋 All Records")
    display = filtered[["id", "disease_type", "confidence", "latitude",
                         "longitude", "timestamp"]].copy()
    display["timestamp"] = display["timestamp"].apply(fmt_ts)
    display["confidence"] = display["confidence"].apply(
        lambda c: f"{CONF_COLOR.get(c, '⚪')} {c}" if c else "—"
    )
    display["photo"] = filtered["photo_path"].apply(
        lambda p: "✅" if pd.notna(p) and p else "—"
    )
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🗑️ Delete a Report")
    del_id = st.number_input("Report ID to delete", min_value=1, step=1)
    if st.button("Delete Report", type="primary"):
        execute("DELETE FROM disease_reports WHERE id = ?", (int(del_id),))
        st.success(f"Deleted report #{del_id}")
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Bot Users
# ─────────────────────────────────────────────────────────────────────────────

elif page == "👥 Bot Users":
    st.title("👥 Bot Users")

    df = query("SELECT * FROM bot_users ORDER BY last_seen DESC")

    if df.empty:
        st.info("No bot users registered yet.")
        st.stop()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Users",  len(df))
    col2.metric("Active",       int(df["is_active"].sum()))
    col3.metric("With Location", int(df["latitude"].notna().sum()))

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        langs = ["All"] + sorted(df["language"].dropna().unique().tolist())
        sel_lang = st.selectbox("Filter by Language", langs)
    with col2:
        active_filter = st.selectbox("Status", ["All", "Active", "Inactive"])

    filtered = df.copy()
    if sel_lang != "All":
        filtered = filtered[filtered["language"] == sel_lang]
    if active_filter == "Active":
        filtered = filtered[filtered["is_active"] == 1]
    elif active_filter == "Inactive":
        filtered = filtered[filtered["is_active"] == 0]

    display = filtered[["chat_id", "telegram_user_id", "language",
                          "latitude", "longitude", "is_active",
                          "created_at", "last_seen"]].copy()
    display["created_at"] = display["created_at"].apply(fmt_ts)
    display["last_seen"]  = display["last_seen"].apply(fmt_ts)
    display["is_active"]  = display["is_active"].apply(lambda x: "✅" if x else "❌")
    display["language"]   = display["language"].apply(
        lambda l: "🇬🇧 EN" if l == "en" else "🇮🇳 KN"
    )

    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🗑️ Deactivate / Delete User")
    col1, col2 = st.columns(2)
    with col1:
        chat_id_input = st.number_input("Chat ID", min_value=0, step=1)
        if st.button("Deactivate User"):
            execute("UPDATE bot_users SET is_active = 0 WHERE chat_id = ?",
                    (int(chat_id_input),))
            st.success(f"Deactivated chat_id {chat_id_input}")
            st.rerun()
    with col2:
        st.write("")
        st.write("")
        if st.button("Delete User", type="primary"):
            execute("DELETE FROM bot_users WHERE chat_id = ?", (int(chat_id_input),))
            st.success(f"Deleted chat_id {chat_id_input}")
            st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Outbreak Alerts
# ─────────────────────────────────────────────────────────────────────────────

elif page == "⚠️ Outbreak Alerts":
    st.title("⚠️ Outbreak Alert History")

    df = query("SELECT * FROM outbreak_notifications ORDER BY triggered_at DESC")

    if df.empty:
        st.info("No outbreak alerts have been sent yet.")
        st.stop()

    col1, col2 = st.columns(2)
    col1.metric("Total Alerts Sent", len(df))

    cutoff_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    recent_24h = df[df["triggered_at"] >= cutoff_24h]
    col2.metric("Last 24 Hours", len(recent_24h))

    st.markdown("---")

    diseases = ["All"] + sorted(df["disease_type"].dropna().unique().tolist())
    sel = st.selectbox("Filter by Disease", diseases)
    filtered = df if sel == "All" else df[df["disease_type"] == sel]

    display = filtered[["id", "disease_type", "center_latitude",
                          "center_longitude", "radius_km", "triggered_at"]].copy()
    display["triggered_at"] = display["triggered_at"].apply(fmt_ts)
    display.columns = ["ID", "Disease", "Lat", "Lon", "Radius (km)", "Triggered At"]

    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📅 Alerts Per Day")
    df["date"] = pd.to_datetime(df["triggered_at"], errors="coerce").dt.date
    timeline = df.groupby("date").size().reset_index(name="Alerts")
    st.bar_chart(timeline.set_index("date"))

    st.markdown("---")
    st.subheader("🗑️ Delete an Alert Record")
    del_id = st.number_input("Alert ID to delete", min_value=1, step=1)
    if st.button("Delete Alert Record", type="primary"):
        execute("DELETE FROM outbreak_notifications WHERE id = ?", (int(del_id),))
        st.success(f"Deleted alert #{del_id}")
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Weather Cache
# ─────────────────────────────────────────────────────────────────────────────

elif page == "🌤️ Weather Cache":
    st.title("🌤️ Weather Snapshots Cache")

    df = query("SELECT * FROM weather_snapshots ORDER BY created_at DESC")

    if df.empty:
        st.info("No weather data cached yet.")
        st.stop()

    col1, col2, col3 = st.columns(3)
    col1.metric("Cached Snapshots", len(df))
    col2.metric("Unique Grid Cells", df["grid_id"].nunique())
    if "temperature_mean" in df.columns and df["temperature_mean"].notna().any():
        col3.metric("Avg Temperature", f"{df['temperature_mean'].mean():.1f}°C")

    st.markdown("---")

    display = df[["id", "grid_id", "latitude", "longitude",
                   "temperature_mean", "humidity_mean", "precipitation_sum",
                   "wind_speed_mean", "source", "created_at"]].copy()
    display["created_at"] = display["created_at"].apply(fmt_ts)
    display.columns = ["ID", "Grid", "Lat", "Lon",
                        "Temp (°C)", "Humidity (%)", "Rain (mm)",
                        "Wind (km/h)", "Source", "Cached At"]

    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("---")
    if st.button("🗑️ Clear All Weather Cache", type="primary"):
        execute("DELETE FROM weather_snapshots")
        st.success("Weather cache cleared.")
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# NDVI Snapshots
# ─────────────────────────────────────────────────────────────────────────────

elif page == "🛰️ NDVI Snapshots":
    st.title("🛰️ NDVI Vegetation Snapshots")

    df = query("SELECT * FROM ndvi_snapshots ORDER BY created_at DESC")

    if df.empty:
        st.info("No NDVI data cached yet.")
        st.stop()

    col1, col2 = st.columns(2)
    col1.metric("Cached Snapshots", len(df))
    col2.metric("Unique Grid Cells", df["grid_id"].nunique())

    st.markdown("---")

    display = df[["id", "grid_id", "latitude", "longitude",
                   "ndvi_mean", "ndvi_change_7d", "ndvi_change_14d",
                   "source", "created_at"]].copy()
    display["created_at"] = display["created_at"].apply(fmt_ts)
    display.columns = ["ID", "Grid", "Lat", "Lon",
                        "NDVI Mean", "Δ 7d", "Δ 14d", "Source", "Cached At"]

    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("---")
    if st.button("🗑️ Clear All NDVI Cache", type="primary"):
        execute("DELETE FROM ndvi_snapshots")
        st.success("NDVI cache cleared.")
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Risk Scores
# ─────────────────────────────────────────────────────────────────────────────

elif page == "📈 Risk Scores":
    st.title("📈 Predictive Risk Scores")

    df = query("SELECT * FROM risk_scores ORDER BY created_at DESC")

    if df.empty:
        st.info("No risk scores recorded yet.")
        st.stop()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Assessments", len(df))
    if "risk_level" in df.columns:
        high_count = len(df[df["risk_level"] == "High"])
        col2.metric("🔴 High Risk", high_count)
        med_count  = len(df[df["risk_level"] == "Medium"])
        col3.metric("🟡 Medium Risk", med_count)

    st.markdown("---")

    levels = ["All"] + sorted(df["risk_level"].dropna().unique().tolist())
    sel = st.selectbox("Filter by Risk Level", levels)
    filtered = df if sel == "All" else df[df["risk_level"] == sel]

    display = filtered[["id", "grid_id", "latitude", "longitude",
                          "risk_score", "risk_level", "created_at"]].copy()
    display["created_at"] = display["created_at"].apply(fmt_ts)
    display["risk_level"] = display["risk_level"].apply(
        lambda l: f"{RISK_COLOR.get(l, '⚪')} {l}" if l else "—"
    )
    display.columns = ["ID", "Grid", "Lat", "Lon",
                        "Score", "Risk Level", "Assessed At"]

    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📋 Reasons (expand a row)")
    for _, row in filtered.head(10).iterrows():
        reasons = []
        try:
            reasons = json.loads(row.get("reason_json") or "[]")
        except Exception:
            pass
        label = (f"{RISK_COLOR.get(row.get('risk_level'), '⚪')} "
                 f"#{row['id']}  Score {row.get('risk_score', '?')}  "
                 f"— {fmt_ts(row.get('created_at', ''))}")
        with st.expander(label):
            if reasons:
                for r in reasons:
                    st.write(f"• {r}")
            else:
                st.write("No reasons stored.")

    st.markdown("---")
    if st.button("🗑️ Clear All Risk Scores", type="primary"):
        execute("DELETE FROM risk_scores")
        st.success("Risk scores cleared.")
        st.rerun()
