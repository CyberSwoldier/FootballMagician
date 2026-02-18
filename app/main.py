"""
Football Betting Probability Flashcards
========================================
Modern navy/silver UI with horizontal flashcard layout
Uses Football-Data.org API (free tier: 10 requests/min)
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date, timedelta
from scipy.stats import poisson
import itertools
import time

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="⚽ Betting Flashcards", layout="wide", initial_sidebar_state="collapsed")

# Navy blue & silver theme with modern styling
st.markdown("""
<style>
    /* Hide Streamlit branding */
    #MainMenu, header, footer {visibility: hidden;}
    .block-container {padding: 0 !important; max-width: 100% !important;}
    [data-testid="stAppViewContainer"] {padding: 0 !important;}
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {width: 6px; height: 6px;}
    ::-webkit-scrollbar-track {background: transparent;}
    ::-webkit-scrollbar-thumb {background: rgba(100, 150, 255, 0.3); border-radius: 3px;}
    ::-webkit-scrollbar-thumb:hover {background: rgba(100, 150, 255, 0.5);}
    
    /* Override Streamlit defaults */
    .stMarkdown {margin: 0 !important;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# API SETUP
# ══════════════════════════════════════════════════════════════════════════════

API_KEY = st.secrets.get("FOOTBALL_DATA_KEY", "")
BASE_URL = "https://api.football-data.org/v4"

COMPETITIONS = {
    "PL": 2021, "PD": 2014, "BL1": 2002, "SA": 2019,
    "FL1": 2015, "PPL": 2017, "CL": 2001,
}

def api_get(endpoint: str, params: dict = None) -> dict:
    if not API_KEY:
        return {}
    headers = {"X-Auth-Token": API_KEY}
    try:
        resp = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params, timeout=15)
        if resp.status_code == 429:
            time.sleep(60)
            resp = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params, timeout=15)
        return resp.json() if resp.status_code == 200 else {}
    except:
        return {}

# ══════════════════════════════════════════════════════════════════════════════
# POISSON MODEL
# ══════════════════════════════════════════════════════════════════════════════

def score_matrix(home_xg: float, away_xg: float, max_goals: int = 6) -> dict:
    matrix = {}
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            matrix[(h, a)] = poisson.pmf(h, home_xg) * poisson.pmf(a, away_xg)
    return matrix

def calculate_markets(home_xg: float, away_xg: float) -> dict:
    matrix = score_matrix(home_xg, away_xg)
    return {
        "Over 0.5 Goals":   sum(p for (h, a), p in matrix.items() if h + a > 0),
        "Over 1.5 Goals":   sum(p for (h, a), p in matrix.items() if h + a > 1),
        "Over 2.5 Goals":   sum(p for (h, a), p in matrix.items() if h + a > 2),
        "Under 3.5 Goals":  sum(p for (h, a), p in matrix.items() if h + a < 4),
        "BTTS":             sum(p for (h, a), p in matrix.items() if h >= 1 and a >= 1),
        "Home Win":         sum(p for (h, a), p in matrix.items() if h > a),
        "Away Win":         sum(p for (h, a), p in matrix.items() if h < a),
        "Draw":             sum(p for (h, a), p in matrix.items() if h == a),
        "Double Chance 1X": sum(p for (h, a), p in matrix.items() if h >= a),
        "Double Chance X2": sum(p for (h, a), p in matrix.items() if h <= a),
    }

# ══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800, show_spinner=False)
def get_todays_fixtures() -> pd.DataFrame:
    if not API_KEY:
        return pd.DataFrame()
    
    today = date.today().strftime("%Y-%m-%d")
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    all_fixtures = []
    
    for comp_code, comp_id in COMPETITIONS.items():
        data = api_get(f"competitions/{comp_id}/matches", {"dateFrom": today, "dateTo": tomorrow})
        for match in data.get("matches", []):
            if match.get("status") not in ["SCHEDULED", "TIMED"]:
                continue
            home_team = match.get("homeTeam", {})
            away_team = match.get("awayTeam", {})
            all_fixtures.append({
                "home": home_team.get("name", "Unknown"),
                "away": away_team.get("name", "Unknown"),
                "home_id": home_team.get("id", 0),
                "away_id": away_team.get("id", 0),
            })
        time.sleep(0.2)
    
    return pd.DataFrame(all_fixtures)

@st.cache_data(ttl=7200, show_spinner=False)
def get_team_xg(team_id: int, home: bool = True) -> float:
    data = api_get(f"teams/{team_id}/matches", {"status": "FINISHED", "limit": 10})
    goals_scored = []
    for match in data.get("matches", []):
        home_team = match.get("homeTeam", {})
        away_team = match.get("awayTeam", {})
        score = match.get("score", {}).get("fullTime", {})
        if home_team.get("id") == team_id:
            goals = score.get("home")
            if goals is not None:
                goals_scored.append(int(goals))
        elif away_team.get("id") == team_id:
            goals = score.get("away")
            if goals is not None:
                goals_scored.append(int(goals))
    if goals_scored:
        return round(sum(goals_scored) / len(goals_scored) * (1.05 if home else 0.95), 2)
    return 1.4 if home else 1.2

def get_mock_fixtures() -> pd.DataFrame:
    teams = [
        ("Arsenal", "Chelsea", 1.8, 1.4), ("Man City", "Liverpool", 2.1, 1.6),
        ("Barcelona", "Real Madrid", 1.9, 1.7), ("PSG", "Bayern Munich", 1.7, 1.8),
        ("Juventus", "AC Milan", 1.5, 1.3), ("Dortmund", "Atalanta", 1.9, 1.5),
        ("Inter", "Napoli", 1.6, 1.4), ("Porto", "Sporting", 1.4, 1.5),
        ("Ajax", "PSV", 1.6, 1.3), ("Atletico", "Sevilla", 1.5, 1.2),
        ("Benfica", "Braga", 1.7, 1.3), ("Roma", "Lazio", 1.6, 1.5),
    ]
    fixtures = []
    for home, away, home_xg, away_xg in teams:
        fixtures.append({"home": home, "away": away, "home_id": hash(home) % 10000,
                        "away_id": hash(away) % 10000, "home_xg": home_xg, "away_xg": away_xg})
    return pd.DataFrame(fixtures)

# ══════════════════════════════════════════════════════════════════════════════
# BET SET GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def generate_flashcards(fixtures: pd.DataFrame, min_single_prob: float = 0.55) -> dict:
    all_bets = []
    for _, row in fixtures.iterrows():
        markets = calculate_markets(row["home_xg"], row["away_xg"])
        match_name = f"{row['home']} vs {row['away']}"
        for market, prob in markets.items():
            if prob >= min_single_prob:
                all_bets.append({"match": match_name, "market": market, "prob": min(prob, 0.99)})
    
    if len(all_bets) < 3:
        return {}
    
    thresholds = [0.70, 0.60, 0.50, 0.40]
    results = {t: [] for t in thresholds}
    
    for combo in itertools.combinations(all_bets, 3):
        if len({b["match"] for b in combo}) < 3:
            continue
        combined = combo[0]["prob"] * combo[1]["prob"] * combo[2]["prob"]
        for threshold in thresholds:
            if combined >= threshold and len(results[threshold]) < 5:
                results[threshold].append({"bets": list(combo), "prob": combined})
    
    for t in thresholds:
        results[t] = sorted(results[t], key=lambda x: x["prob"], reverse=True)[:5]
    
    return results

# ══════════════════════════════════════════════════════════════════════════════
# UI - NAVY BLUE & SILVER THEME
# ══════════════════════════════════════════════════════════════════════════════

# Header
st.markdown("""
<div style="
    background: linear-gradient(135deg, rgba(4, 13, 26, 0.98), rgba(7, 20, 40, 0.95));
    padding: 24px 36px;
    border-bottom: 1px solid rgba(100, 160, 255, 0.15);
    margin-bottom: 0;
">
    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 8px;">
        <div style="
            width: 42px; height: 42px;
            background: linear-gradient(135deg, #1a3a70, #4da8ff);
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 22px;
            box-shadow: 0 0 20px rgba(77, 168, 255, 0.4);
        ">⚽</div>
        <div>
            <div style="
                font-family: 'Bebas Neue', sans-serif;
                font-size: 32px; letter-spacing: 2px;
                color: #e8edf5; line-height: 1;
            ">PROBABILITY ENGINE</div>
            <div style="
                font-size: 11px; letter-spacing: 2px;
                color: #8899bb; text-transform: uppercase; margin-top: 4px;
            ">Football Betting Analytics</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Fetch data
use_mock = st.sidebar.checkbox("📊 Use Mock Data", value=not bool(API_KEY))

with st.spinner("Loading fixtures..."):
    if use_mock or not API_KEY:
        fixtures = get_mock_fixtures()
    else:
        fixtures = get_todays_fixtures()
        if fixtures.empty:
            fixtures = get_mock_fixtures()
        else:
            with st.spinner("Calculating probabilities..."):
                fixtures["home_xg"] = fixtures["home_id"].apply(lambda x: get_team_xg(x, home=True))
                fixtures["away_xg"] = fixtures["away_id"].apply(lambda x: get_team_xg(x, home=False))

flashcards = generate_flashcards(fixtures, min_single_prob=0.55)

if not flashcards or all(len(cards) == 0 for cards in flashcards.values()):
    st.error("❌ No bet sets found")
    st.stop()

# Threshold selector (modern pill buttons)
st.markdown("""
<div style="
    background: rgba(7, 20, 40, 0.6);
    padding: 20px 36px;
    border-bottom: 1px solid rgba(100, 160, 255, 0.1);
">
    <div style="display: flex; align-items: center; gap: 16px;">
        <span style="
            font-size: 11px; letter-spacing: 2.5px;
            text-transform: uppercase; color: #8899bb;
        ">THRESHOLD</span>
""", unsafe_allow_html=True)

# Threshold pills with session state
if 'active_threshold' not in st.session_state:
    st.session_state.active_threshold = 0.70

col1, col2, col3, col4, _ = st.columns([1, 1, 1, 1, 6])

threshold_config = {
    0.70: ("≥70%", "#1eff8e", col1),
    0.60: ("≥60%", "#4da8ff", col2),
    0.50: ("≥50%", "#f0c55a", col3),
    0.40: ("≥40%", "#ff8c42", col4),
}

for threshold, (label, color, col) in threshold_config.items():
    with col:
        active = "active" if st.session_state.active_threshold == threshold else ""
        if st.button(label, key=f"thr_{threshold}", use_container_width=True):
            st.session_state.active_threshold = threshold
            st.rerun()

st.markdown("""
    </div>
</div>
""", unsafe_allow_html=True)

# Add custom button styles
st.markdown(f"""
<style>
    [data-testid="column"] button {{
        background: transparent !important;
        border: 1px solid rgba(100, 160, 255, 0.2) !important;
        color: #8899bb !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        padding: 8px 16px !important;
        border-radius: 8px !important;
        transition: all 0.2s !important;
    }}
    [data-testid="column"] button:hover {{
        border-color: rgba(100, 160, 255, 0.4) !important;
        color: #e8edf5 !important;
    }}
    /* Active state based on threshold */
    [data-testid="column"]:nth-child({list(threshold_config.keys()).index(st.session_state.active_threshold) + 1}) button {{
        background: linear-gradient(135deg, rgba(30, 80, 180, 0.5), rgba(20, 50, 120, 0.6)) !important;
        border-color: {threshold_config[st.session_state.active_threshold][1]}80 !important;
        color: #e8edf5 !important;
        box-shadow: 0 0 20px {threshold_config[st.session_state.active_threshold][1]}40 !important;
    }}
</style>
""", unsafe_allow_html=True)

# Main content area
st.markdown("""
<div style="
    background: #040d1a;
    min-height: calc(100vh - 200px);
    padding: 32px 36px;
">
""", unsafe_allow_html=True)

# Get active threshold data
active_threshold = st.session_state.active_threshold
active_color = threshold_config[active_threshold][1]
cards = flashcards.get(active_threshold, [])

if not cards:
    st.markdown(f"""
    <div style="
        background: rgba(10, 20, 45, 0.7);
        border: 1px dashed rgba(240, 197, 90, 0.4);
        border-radius: 16px;
        padding: 60px 32px;
        text-align: center;
    ">
        <div style="font-size: 48px; margin-bottom: 16px; opacity: 0.6;">⚠️</div>
        <div style="
            font-family: 'Bebas Neue', sans-serif;
            font-size: 28px; letter-spacing: 2px;
            color: #f0c55a; margin-bottom: 12px;
        ">No Sets Above {active_threshold*100:.0f}%</div>
        <div style="font-size: 14px; color: #8899bb; line-height: 1.7; max-width: 500px; margin: 0 auto;">
            No bet sets meet the {active_threshold*100:.0f}% probability threshold today.
            Try selecting a lower threshold above.
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    # Display flashcards in grid (3 per row)
    for i in range(0, len(cards), 3):
        row_cards = cards[i:i+3]
        cols = st.columns(3)
        
        for j, card in enumerate(row_cards):
            with cols[j]:
                prob_pct = card["prob"] * 100
                
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, rgba(12, 28, 60, 0.9), rgba(10, 20, 50, 0.95));
                    border: 1px solid rgba(100, 160, 255, 0.12);
                    border-radius: 14px;
                    padding: 20px;
                    margin-bottom: 20px;
                    transition: transform 0.2s, box-shadow 0.2s;
                    height: 100%;
                    display: flex;
                    flex-direction: column;
                " onmouseover="this.style.transform='translateY(-4px)'; this.style.boxShadow='0 12px 40px rgba(0,0,0,0.4), 0 0 0 1px {active_color}40';"
                   onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none';">
                    
                    <!-- Card header -->
                    <div style="
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        margin-bottom: 16px;
                        padding-bottom: 14px;
                        border-bottom: 1px solid rgba(100, 160, 255, 0.08);
                    ">
                        <div style="
                            font-family: 'Bebas Neue', sans-serif;
                            font-size: 20px;
                            letter-spacing: 1px;
                            color: #8899bb;
                        ">SET #{i+j+1}</div>
                        <div style="
                            font-family: 'Bebas Neue', sans-serif;
                            font-size: 32px;
                            letter-spacing: 1px;
                            color: {active_color};
                            text-shadow: 0 0 20px {active_color}60;
                        ">{prob_pct:.1f}%</div>
                    </div>
                    
                    <!-- 3 bets -->
                    <div style="flex: 1; display: flex; flex-direction: column; gap: 10px;">
                """, unsafe_allow_html=True)
                
                for bet in card["bets"]:
                    st.markdown(f"""
                    <div style="
                        background: rgba(20, 40, 80, 0.4);
                        padding: 12px;
                        border-radius: 8px;
                        border-left: 3px solid {active_color};
                    ">
                        <div style="
                            font-size: 13px;
                            font-weight: 600;
                            color: #d0d8e8;
                            margin-bottom: 6px;
                        ">{bet['match']}</div>
                        <div style="
                            font-size: 11px;
                            color: #8899bb;
                            margin-bottom: 6px;
                        ">{bet['market']}</div>
                        <div style="
                            font-family: 'JetBrains Mono', monospace;
                            font-size: 14px;
                            font-weight: 600;
                            color: {active_color};
                        ">{bet['prob']*100:.1f}%</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("</div></div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.markdown("""
<div style="
    background: rgba(7, 20, 40, 0.8);
    padding: 16px 36px;
    border-top: 1px solid rgba(100, 160, 255, 0.1);
    text-align: center;
">
    <div style="font-size: 11px; color: #8899bb; letter-spacing: 0.5px;">
        💡 Probabilities calculated using Poisson distribution · ⚠️ For entertainment only
    </div>
</div>
""", unsafe_allow_html=True)
