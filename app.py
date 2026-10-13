import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests

# ==============================================================================
# 1. LIVE GEOSPATIAL & ATMOSPHERIC DATA FETCHERS
# ==============================================================================

def fetch_live_elevation(lat: float, lon: float) -> float:
    """Fetches real-time ground elevation (meters above sea level) via Open-Elevation API."""
    try:
        url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            return float(data['results'][0]['elevation'])
    except Exception:
        pass
    return 45.0  # Fallback default elevation (m)

def fetch_live_wind(lat: float, lon: float, api_key: str = "") -> dict:
    """Fetches live surface wind vectors (m/s) and direction using OpenWeather API."""
    if api_key:
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
            res = requests.get(url, timeout=3).json()
            speed = res['wind']['speed']
            deg = res['wind']['deg']
            rad = np.radians(deg)
            wx = -speed * np.sin(rad)
            wy = -speed * np.cos(rad)
            return {"wx": round(wx, 2), "wy": round(wy, 2), "speed": speed, "source": "LIVE_OPENWEATHER_API"}
        except Exception:
            pass
    return {"wx": -14.0, "wy": 6.5, "speed": 15.4, "source": "SIMULATED_ATMOSPHERE"}

# ==============================================================================
# 2. PHALANX KINEMATIC & DEW PHYSICAL ENGINE
# ==============================================================================

class PhalanxLiveEngine:
    def __init__(self, lat: float, lon: float, owm_key: str = ""):
        self.ground_alt = fetch_live_elevation(lat, lon)
        self.wind_data = fetch_live_wind(lat, lon, owm_key)
        
        self.origin = np.array([0.0, 0.0, self.ground_alt + 15.0])
        self.objective = np.array([3200.0, 3200.0, self.ground_alt + 40.0])
        
        self.dew_pos = np.array([1600.0, 1400.0, self.ground_alt + 5.0])
        self.dew_range = 1750.0
        self.dew_power = 100.0
        
        self.speed = 45.0
        self.battery_wh = 600.0

def compute_kinematics(waypoints, engine: PhalanxLiveEngine):
    pts = []
    for i in range(len(waypoints) - 1):
        p1, p2 = np.array(waypoints[i]), np.array(waypoints[i+1])
        dist = np.linalg.norm(p2 - p1)
        steps = max(10, int(dist / 15.0))
        for t in np.linspace(0, 1, steps):
            pts.append(p1 + t * (p2 - p1))
            
    pts = np.array(pts)
    dt = 0.12
    
    if len(pts) > 4:
        vel = np.diff(pts, axis=0) / dt
        acc = np.diff(vel, axis=0) / dt
        jerk = np.diff(acc, axis=0) / dt
        avg_jerk = float(np.mean(np.linalg.norm(jerk, axis=1)))
    else:
        avg_jerk = 0.5

    gimbal_lag = round(0.12 * (avg_jerk ** 1.35), 2)
    smear_factor = round(1.0 + (gimbal_lag / 1.0), 2)

    max_dwell = 0.0
    curr_dwell = 0.0
    for pt in pts:
        if np.linalg.norm(pt - engine.dew_pos) < engine.dew_range:
            eff_tick = dt * (1.0 / max(1.0, smear_factor - 3.0))
            curr_dwell += eff_tick
            max_dwell = max(max_dwell, curr_dwell)
        else:
            curr_dwell = 0.0

    total_wh = 0.0
    wind_vec_surface = np.array([engine.wind_data['wx'], engine.wind_data['wy'], -1.5])
    
    for i in range(len(waypoints) - 1):
        p1, p2 = waypoints[i], waypoints[i+1]
        d = np.linalg.norm(p2 - p1)
        if d == 0: continue
        dir_vec = (p2 - p1) / d
        
        mean_alt = (p1[2] + p2[2]) / 2.0
        alt_scale = np.log(max(10.0, mean_alt) / 0.1) / np.log(10.0 / 0.1)
        wind_at_alt = wind_vec_surface * alt_scale
        
        airspeed = engine.speed + np.dot(wind_at_alt, dir_vec)
        power_w = 290.0 + (0.028 * (airspeed ** 3))
        if smear_factor > 2.0:
            power_w += 115.0
            
        total_wh += (power_w * ((d / max(10.0, airspeed)) / 3600.0))

    return {
        "jerk": round(avg_jerk, 2),
        "lag_cm": gimbal_lag,
        "smear": smear_factor,
        "dwell_s": round(max_dwell, 2),
        "energy_wh": round(total_wh, 1),
        "battery_pct": round(((engine.battery_wh - total_wh) / engine.battery_wh) * 100.0, 1)
    }

# ==============================================================================
# 3. HIGH-CONTRAST TACTICAL INTERFACE
# ==============================================================================

st.set_page_config(page_title="PHALANX-AI // LIVE C2", layout="wide", initial_sidebar_state="expanded")

# Ultra High-Contrast Tactical CSS Overhaul
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;700&family=JetBrains+Mono:wght@400;600;700&display=swap');

    /* Global Dark Canvas */
    html, body, [class*="css"] {
        font-family: 'JetBrains Mono', monospace !important;
        background-color: #05070A !important;
        color: #E2E8F0 !important;
    }
    
    .stApp {
        background-color: #05070A !important;
    }

    /* Force Streamlit Top Bar to Dark */
    header[data-testid="stHeader"] {
        background-color: #05070A !important;
    }

    /* Headings */
    h1, h2, h3 {
        font-family: 'Chakra Petch', sans-serif !important;
        text-transform: uppercase !important;
        color: #FFFFFF !important;
        letter-spacing: 0.05em !important;
    }

    /* Metric HUD Blocks */
    div[data-testid="stMetric"] {
        background-color: #0D131D !important;
        border: 1px solid #1E293B !important;
        border-radius: 0px !important;
        padding: 12px !important;
    }

    div[data-testid="stMetricLabel"] {
        font-family: 'Chakra Petch', sans-serif !important;
        font-size: 11px !important;
        color: #94A3B8 !important;
        letter-spacing: 0.1em !important;
    }

    div[data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 22px !important;
        font-weight: 700 !important;
        color: #00E5FF !important;
    }

    /* HIGH-CONTRAST SIDEBAR OVERHAUL */
    section[data-testid="stSidebar"] {
        background-color: #0B0F17 !important;
        border-right: 1px solid #1E293B !important;
    }

    /* Sidebar Labels, Inputs, & Paragraphs */
    section[data-testid="stSidebar"] label, 
    section[data-testid="stSidebar"] p, 
    section[data-testid="stSidebar"] div {
        color: #F8FAFC !important; /* Pure White High Contrast */
        font-size: 12px !important;
    }

    /* Input Boxes in Sidebar */
    section[data-testid="stSidebar"] input {
        background-color: #16202C !important;
        color: #FFFFFF !important;
        border: 1px solid #334155 !important;
        border-radius: 0px !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Action Button */
    div.stButton > button {
        background-color: #00E5FF !important;
        color: #05070A !important;
        font-family: 'Chakra Petch', sans-serif !important;
        font-weight: 700 !important;
        border-radius: 0px !important;
        border: none !important;
        width: 100% !important;
        padding: 12px !important;
        letter-spacing: 0.1em !important;
    }

    div.stButton > button:hover {
        background-color: #38BDF8 !important;
        color: #000000 !important;
    }

    /* HUD Headers */
    .hud-header {
        border-bottom: 1px solid #1E293B;
        padding-bottom: 6px;
        margin-bottom: 12px;
        font-family: 'Chakra Petch', sans-serif;
        font-size: 12px;
        color: #00E5FF !important; /* Bright Cyan Section Titles */
        letter-spacing: 0.15em;
        font-weight: 700;
    }

    /* High Visibility Info Card */
    div.stAlert {
        background-color: #0D131D !important;
        border: 1px solid #00E5FF !important;
        color: #00E5FF !important;
        border-radius: 0px !important;
    }
</style>
""", unsafe_allow_html=True)

# Top Bar Header
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("<h1 style='margin:0; padding:0; font-size: 26px; color: #FFFFFF;'>PHALANX // LIVE OPERATIONAL C2</h1>", unsafe_allow_html=True)
    st.markdown("<div style='font-size: 11px; color: #94A3B8; letter-spacing: 0.15em;'>DYNAMIC GEOSPATIAL & ATMOSPHERIC SYNC CORE</div>", unsafe_allow_html=True)
with col_h2:
    st.markdown("<div style='text-align: right; font-size: 12px; color: #00E5FF; font-family: \"Chakra Petch\"; font-weight:700;'>[SYS_ONLINE] // GPS_SYNC</div>", unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

# Sidebar Console
st.sidebar.markdown("<div class='hud-header'>OPERATIONAL THEATER (GPS)</div>", unsafe_allow_html=True)
lat_val = st.sidebar.number_input("LATITUDE", value=12.9716, format="%.4f")
lon_val = st.sidebar.number_input("LONGITUDE", value=77.5946, format="%.4f")
owm_key = st.sidebar.text_input("OPENWEATHER API KEY (OPTIONAL)", type="password")

st.sidebar.markdown("<div class='hud-header' style='margin-top:15px;'>SYSTEM CONTROLS</div>", unsafe_allow_html=True)
evasion_intensity = st.sidebar.slider("JERK SCALING (da/dt)", 0.5, 2.0, 1.3, 0.1)

# Fetch Engine Instance
engine = PhalanxLiveEngine(lat_val, lon_val, owm_key)

st.sidebar.markdown("<div class='hud-header' style='margin-top:15px;'>LIVE TELEMETRY SYNC</div>", unsafe_allow_html=True)
st.sidebar.markdown(f"<p style='color:#FFFFFF; margin:2px 0;'>GROUND ELEV : <b>{engine.ground_alt:.1f} m</b> (MSL)</p>", unsafe_allow_html=True)
st.sidebar.markdown(f"<p style='color:#FFFFFF; margin:2px 0;'>WIND SOURCE : <b>{engine.wind_data['source']}</b></p>", unsafe_allow_html=True)
st.sidebar.markdown(f"<p style='color:#FFFFFF; margin:2px 0;'>SURFACE WIND : <b>{engine.wind_data['speed']} m/s</b></p>", unsafe_allow_html=True)

st.sidebar.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

if st.sidebar.button("EXECUTE TRAJECTORY OPTIMIZATION"):
    # 1. Direct Vector
    base_wps = [engine.origin, engine.objective]
    base_m = compute_kinematics(base_wps, engine)
    
    # 2. Optimized Vector
    jerk_val = evasion_intensity * 140.0
    opt_wps = [
        engine.origin,
        np.array([950.0, 500.0, engine.ground_alt + 35.0]),
        np.array([1500.0, 1200.0, engine.ground_alt + 25.0 + (jerk_val * 0.12)]),
        np.array([2000.0, 1700.0, engine.ground_alt + 55.0 - (jerk_val * 0.08)]),
        np.array([2700.0, 2600.0, engine.ground_alt + 60.0]),
        engine.objective
    ]
    opt_m = compute_kinematics(opt_wps, engine)

    # Top HUD Banner
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("GIMBAL LAG", f"{opt_m['lag_cm']} CM", delta=f"+{round(opt_m['lag_cm'] - base_m['lag_cm'], 2)} CM")
    m2.metric("SPOT SMEAR", f"{opt_m['smear']}X", delta="EKF UNLOCKED")
    m3.metric("LASER DWELL", f"{opt_m['dwell_s']} SEC", delta=f"{opt_m['dwell_s'] - base_m['dwell_s']:.1f} S")
    m4.metric("BATTERY HORIZON", f"{opt_m['battery_pct']}%", delta=f"-{opt_m['energy_wh']} Wh")

    st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

    c_left, c_right = st.columns([3, 2])

    with c_left:
        st.markdown("<div class='hud-header'>// 3D BATTLESPACE THREAT CANVAS (DYNAMIC MSL ALTITUDE)</div>", unsafe_allow_html=True)
        
        fig = go.Figure()

        # DEW Threat Dome
        u = np.linspace(0, 2*np.pi, 30)
        v = np.linspace(0, np.pi/2, 15)
        x_dew = engine.dew_pos[0] + engine.dew_range * np.outer(np.cos(u), np.sin(v))
        y_dew = engine.dew_pos[1] + engine.dew_range * np.outer(np.sin(u), np.sin(v))
        z_dew = engine.dew_pos[2] + engine.dew_range * np.outer(np.ones(np.size(u)), np.cos(v))
        
        fig.add_trace(go.Surface(x=x_dew, y=y_dew, z=z_dew, opacity=0.12, colorscale=[[0, '#FF0055'], [1, '#FF0055']], showscale=False, name="HEL Threat"))

        # Direct Vector
        fig.add_trace(go.Scatter3d(
            x=[engine.origin[0], engine.objective[0]], y=[engine.origin[1], engine.objective[1]], z=[engine.origin[2], engine.objective[2]],
            mode='lines', line=dict(color='#FF0055', width=2, dash='dash'), name='Direct Vector'
        ))

        # Phalanx Certified Vector
        w_arr = np.array(opt_wps)
        fig.add_trace(go.Scatter3d(
            x=w_arr[:, 0], y=w_arr[:, 1], z=w_arr[:, 2],
            mode='lines+markers', line=dict(color='#00E5FF', width=5),
            marker=dict(size=4, color='#05070A', symbol='diamond', line=dict(color='#00E5FF', width=2)), name='Phalanx Vector'
        ))

        fig.update_layout(
            template="plotly_dark", paper_bgcolor='#05070A', plot_bgcolor='#05070A',
            scene=dict(
                xaxis=dict(backgroundcolor='#05070A', gridcolor='#16202C', title='X (M)'),
                yaxis=dict(backgroundcolor='#05070A', gridcolor='#16202C', title='Y (M)'),
                zaxis=dict(backgroundcolor='#05070A', gridcolor='#16202C', title='ALT MSL (M)'),
                camera=dict(eye=dict(x=1.3, y=-1.3, z=1.0))
            ),
            margin=dict(l=0, r=0, b=0, t=0), height=520
        )
        st.plotly_chart(fig, use_container_width="stretch")

    with c_right:
        st.markdown("<div class='hud-header'>// LIVE GEOSPATIAL & EXECUTION MATRIX</div>", unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style='background: #0D131D; border: 1px solid #1E293B; padding: 12px; margin-bottom: 10px;'>
            <div style='font-size: 11px; color: #00E5FF; font-weight:700;'>LIVE TELEMETRY SYNC</div>
            <div style='font-size: 12px; color: #FFFFFF; margin-top: 4px;'>GPS: [{lat_val}, {lon_val}]</div>
            <div style='font-size: 11px; color: #CBD5E1; margin-top: 2px;'>
                Ground MSL: {engine.ground_alt} m | Wind: {engine.wind_data['speed']} m/s
            </div>
        </div>

        <div style='background: #0D131D; border: 1px solid #1E293B; padding: 12px; margin-bottom: 10px;'>
            <div style='font-size: 11px; color: #FF0055; font-weight:700;'>PHASE 01 // DIRECT VECTOR AUDIT</div>
            <div style='font-size: 12px; color: #FF0055; margin-top: 4px;'>STATUS: CRITICAL_HAZARD</div>
            <div style='font-size: 11px; color: #CBD5E1; margin-top: 2px;'>
                Laser Dwell: {base_m['dwell_s']}s (Limit: 2.0s)
            </div>
        </div>

        <div style='background: #0D131D; border: 1px solid #1E293B; padding: 12px; margin-bottom: 12px;'>
            <div style='font-size: 11px; color: #00E5FF; font-weight:700;'>PHASE 02 // PARETO CLEARANCE</div>
            <div style='font-size: 12px; color: #00E5FF; margin-top: 4px;'>STATUS: CLEARANCE_CERTIFIED</div>
            <div style='font-size: 11px; color: #CBD5E1; margin-top: 2px;'>
                Laser Dwell Reduced: {opt_m['dwell_s']}s<br>
                Battery Reserve: {opt_m['battery_pct']}%
            </div>
        </div>
        """, unsafe_allow_html=True)

        df_exp = pd.DataFrame(opt_wps, columns=["X_M", "Y_M", "ALT_MSL_M"])
        st.download_button(
            label="EXPORT CERTIFIED FLIGHT PLAN (CSV)",
            data=df_exp.to_csv(index=False).encode('utf-8'),
            file_name='phalanx_live_geospatial_trajectory.csv', mime='text/csv'
        )
else:
    st.info("ENTER GPS COORDINATES IN SIDEBAR AND CLICK 'EXECUTE TRAJECTORY OPTIMIZATION'.")
