"""
map_dashboard.py - Streamlit + Folium outbreak map for CropRadar

Run:
  streamlit run map_dashboard.py
"""

import os
from datetime import datetime

import folium
import pandas as pd
import requests
import streamlit as st
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_BASE_URL = os.environ.get("CROPRADAR_API_URL", "http://localhost:8000")

OUTBREAK_THRESHOLD = 3
OUTBREAK_WINDOW_HRS = 48

# Color palette per disease (extends with grey for unknowns)
DISEASE_COLORS = {
    "Leaf Blight":    "#e74c3c",
    "Powdery Mildew": "#9b59b6",
    "Leaf Spot":      "#e67e22",
    "Rust":           "#c0392b",
    "Healthy Leaf":   "#27ae60",
}
DEFAULT_COLOR = "#7f8c8d"

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def load_reports() -> pd.DataFrame:
    """Fetch all reports from the CropRadar API and return a DataFrame."""
    try:
        resp = requests.get(f"{API_BASE_URL}/reports", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception as exc:
        st.error(f"❌ Could not fetch data from backend: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=30)
def load_alerts() -> list[dict]:
    """Fetch outbreak alert data from the /alerts endpoint."""
    try:
        resp = requests.get(f"{API_BASE_URL}/alerts", timeout=10)
        resp.raise_for_status()
        return resp.json().get("outbreaks", [])
    except Exception:
        return []


def get_color(disease_name: str) -> str:
    return DISEASE_COLORS.get(disease_name, DEFAULT_COLOR)


def hex_to_folium_color(hex_color: str) -> str:
    """Map hex to the nearest named Folium marker color."""
    mapping = {
        "#e74c3c": "red",
        "#9b59b6": "purple",
        "#e67e22": "orange",
        "#c0392b": "darkred",
        "#27ae60": "green",
        "#7f8c8d": "gray",
    }
    return mapping.get(hex_color, "blue")


# ---------------------------------------------------------------------------
# Map builder
# ---------------------------------------------------------------------------

def build_map(df: pd.DataFrame, outbreak_diseases: set) -> folium.Map:
    """Build and return a Folium map with disease markers."""
    # Centre the map on mean coordinates, or a default
    if df.empty or df[["latitude", "longitude"]].dropna().empty:
        center = [20.5937, 78.9629]  # centre of India as default
        zoom = 5
    else:
        valid = df[["latitude", "longitude"]].dropna()
        center = [valid["latitude"].mean(), valid["longitude"].mean()]
        zoom = 6

    m = folium.Map(location=center, zoom_start=zoom, tiles="CartoDB positron")

    # Separate cluster per disease type for easy visual grouping
    clusters: dict[str, MarkerCluster] = {}
    for disease in df["disease_type"].unique() if not df.empty else []:
        clusters[disease] = MarkerCluster(name=disease).add_to(m)

    for _, row in df.iterrows():
        lat = row.get("latitude")
        lon = row.get("longitude")
        if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
            continue

        disease   = row["disease_type"]
        color     = get_color(disease)
        f_color   = hex_to_folium_color(color)
        is_outbreak = disease in outbreak_diseases

        # Larger, pulsing icon for outbreak clusters
        icon = folium.Icon(
            color="red" if is_outbreak else f_color,
            icon="exclamation-sign" if is_outbreak else "leaf",
            prefix="glyphicon",
        )

        popup_html = f"""
        <div style="min-width:180px;font-family:sans-serif;">
          <b style="color:{color};">{disease}</b><br/>
          <b>Confidence:</b> {row.get('confidence', 'N/A')}<br/>
          <b>Remedy:</b> {row.get('remedy', 'N/A')}<br/>
          <b>Time:</b> {row.get('timestamp', 'N/A')}<br/>
          {"<br/><span style='color:red;font-weight:bold;'>⚠️ OUTBREAK AREA</span>" if is_outbreak else ""}
        </div>
        """

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{disease} ({'OUTBREAK' if is_outbreak else row.get('confidence','?')} confidence)",
            icon=icon,
        ).add_to(clusters.get(disease, m))

    folium.LayerControl().add_to(m)
    return m


# ---------------------------------------------------------------------------
# Streamlit app
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="CropRadar – Outbreak Map",
    page_icon="🌾",
    layout="wide",
)

# ---- Header ---------------------------------------------------------------
st.markdown(
    """
    <style>
      .header {background:linear-gradient(90deg,#27ae60,#2ecc71);
               padding:1.2rem 1.5rem;border-radius:10px;margin-bottom:1rem;}
      .header h1 {color:white;margin:0;font-size:2rem;}
      .header p  {color:#d5f5e3;margin:0;}
      .metric-card {background:#f9f9f9;border-left:4px solid #27ae60;
                    padding:.8rem 1rem;border-radius:6px;}
    </style>
    <div class="header">
      <h1>🌾 CropRadar – Outbreak Map</h1>
      <p>Real-time crop disease surveillance dashboard</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- Load data ------------------------------------------------------------
df       = load_reports()
outbreaks = load_alerts()
outbreak_diseases = {o["disease_type"] for o in outbreaks}

# ---- Sidebar filters -------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/plant-under-sun.png", width=80)
    st.title("Filters")

    if not df.empty:
        diseases  = ["All"] + sorted(df["disease_type"].unique().tolist())
        sel_disease = st.selectbox("Disease", diseases)

        date_range = st.date_input(
            "Date range",
            value=(df["timestamp"].min().date(), df["timestamp"].max().date()),
        )
    else:
        sel_disease = "All"
        date_range  = None

    st.markdown("---")
    st.caption(f"API: `{API_BASE_URL}`")
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

# ---- Apply filters --------------------------------------------------------
filtered = df.copy() if not df.empty else df

if not filtered.empty and sel_disease != "All":
    filtered = filtered[filtered["disease_type"] == sel_disease]

if not filtered.empty and date_range and len(date_range) == 2:
    start, end = date_range
    filtered = filtered[
        (filtered["timestamp"].dt.date >= start) &
        (filtered["timestamp"].dt.date <= end)
    ]

# ---- KPIs -----------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
total_reports   = len(filtered)
disease_types   = filtered["disease_type"].nunique() if not filtered.empty else 0
outbreak_count  = len(outbreaks)
latest_ts       = (
    filtered["timestamp"].max().strftime("%Y-%m-%d %H:%M")
    if not filtered.empty else "—"
)

col1.metric("📋 Total Reports", total_reports)
col2.metric("🦠 Disease Types", disease_types)
col3.metric("⚠️ Active Outbreaks", outbreak_count)
col4.metric("🕒 Latest Report", latest_ts)

# ---- Outbreak banners -----------------------------------------------------
if outbreaks:
    for ob in outbreaks:
        st.error(
            f"⚠️ **Outbreak Alert:** *{ob['disease_type']}* — "
            f"**{ob['count']} reports** in the last {OUTBREAK_WINDOW_HRS}h"
        )
else:
    st.success("✅ No active outbreaks detected.")

# ---- Map + Table layout ---------------------------------------------------
map_col, table_col = st.columns([3, 2])

with map_col:
    st.subheader("📍 Disease Report Map")
    fmap = build_map(filtered, outbreak_diseases)
    st_folium(fmap, width=None, height=520, returned_objects=[])

with table_col:
    st.subheader("📊 Recent Reports")
    if not filtered.empty:
        display_cols = ["disease_type", "confidence", "latitude", "longitude", "timestamp"]
        display_cols = [c for c in display_cols if c in filtered.columns]
        st.dataframe(
            filtered[display_cols].sort_values("timestamp", ascending=False).head(50),
            use_container_width=True,
            height=520,
        )
    else:
        st.info("No reports found. Send a crop photo to the Telegram bot to get started!")

# ---- Disease breakdown chart ----------------------------------------------
if not filtered.empty:
    st.subheader("📈 Disease Breakdown")
    disease_counts = filtered["disease_type"].value_counts().reset_index()
    disease_counts.columns = ["Disease", "Count"]
    st.bar_chart(disease_counts.set_index("Disease"), use_container_width=True, height=260)

# ---- Footer ---------------------------------------------------------------
st.markdown(
    "<hr/><p style='text-align:center;color:#aaa;font-size:0.8rem;'>"
    "CropRadar – AI-powered crop disease surveillance | Hackathon MVP</p>",
    unsafe_allow_html=True,
)
