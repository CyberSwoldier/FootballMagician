"""
Football Betting Probability Flashcards
========================================
Uses Football-Data.org API (free tier: 10 requests/min, no credit card)

Setup:
1. Get free key: https://www.football-data.org/client/register
2. Add to .streamlit/secrets.toml:
       FOOTBALL_DATA_KEY = "your_key_here"
3. Run: streamlit run betting_app.py
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

st.markdown("""
<style>
    #MainMenu, header, footer {visibility: hidden;}
    .block-container {padding-top: 1.5rem;}
    h1 {font-size: 2.5rem; margin-bottom: 0.5rem;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# API SETUP
# ══════════════════════════════════════════════════════════════════════════════

API_KEY = st.secrets.get("FOOTBALL_DATA_KEY", "")
BASE_URL = "https://api.football-data.org/v4"

# Top European competitions (Football-Data IDs)
COMPETITIONS = {
    "PL": 2021,   # Premier League
    "PD": 2014,   # La Liga
    "BL1": 2002,  # Bundesliga
    "SA": 2019,   # Serie A
    "FL1": 2015,  # Ligue 1
    "PPL": 2017,  # Primeira Liga
    "CL": 2001,   # Champions League
}

def api_get(endpoint: str, params: dict = None) -> dict:
    """Call Football-Data.org with error handling."""
    if not API_KEY:
        return {}
    
    headers = {"X-Auth-Token": API_KEY}
    
    try:
        resp = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params, timeout=15)
        if resp.status_code == 429:
            st.warning("⚠️ Rate limit hit. Waiting 60s...")
            time.sleep(60)
            resp = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params, timeout=15)
        
        if resp.status_code != 200:
            st.warning(f"⚠️ API returned {resp.status_code}")
            return {}
        
        return resp.json()
    except Exception as e:
        st.error(f"❌ API error: {e}")
        return {}

# ══════════════════════════════════════════════════════════════════════════════
# POISSON MODEL
# ══════════════════════════════════════════════════════════════════════════════

def score_matrix(home_xg: float, away_xg: float, max_goals: int = 6) -> dict:
    """Probability matrix for all scorelines."""
    matrix = {}
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            prob = poisson.pmf(h, home_xg) * poisson.pmf(a, away_xg)
            matrix[(h, a)] = prob
    return matrix

def calculate_markets(home_xg: float, away_xg: float) -> dict:
    """Calculate all betting market probabilities."""
    matrix = score_matrix(home_xg, away_xg)
    
    return {
        "Over 0.5 Goals":   sum(p for (h, a), p in matrix.items() if h + a > 0),
        "Over 1.5 Goals":   sum(p for (h, a), p in matrix.items() if h + a > 1),
        "Over 2.5 Goals":   sum(p for (h, a), p in matrix.items() if h + a > 2),
        "Under 3.5 Goals":  sum(p for (h, a), p in matrix.items() if h + a < 4),
        "Under 4.5 Goals":  sum(p for (h, a), p in matrix.items() if h + a < 5),
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
    """Fetch today's fixtures from Football-Data.org."""
    if not API_KEY:
        return pd.DataFrame()
    
    today = date.today().strftime("%Y-%m-%d")
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    all_fixtures = []
    
    # Fetch from each competition
    for comp_code, comp_id in COMPETITIONS.items():
        data = api_get(f"competitions/{comp_id}/matches", {
            "dateFrom": today,
            "dateTo": tomorrow,
        })
        
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
                "competition": comp_code,
            })
        
        time.sleep(0.2)  # Respect rate limit
    
    return pd.DataFrame(all_fixtures)

@st.cache_data(ttl=7200, show_spinner=False)
def get_team_xg(team_id: int, home: bool = True) -> float:
    """
    Estimate xG from team's recent matches.
    Football-Data.org doesn't have xG, so we use goals scored/conceded.
    """
    data = api_get(f"teams/{team_id}/matches", {
        "status": "FINISHED",
        "limit": 10,
    })
    
    goals_scored = []
    matches = data.get("matches", [])
    
    for match in matches:
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
        avg = sum(goals_scored) / len(goals_scored)
        return round(avg * (1.05 if home else 0.95), 2)
    
    return 1.4 if home else 1.2

def get_mock_fixtures() -> pd.DataFrame:
    """Fallback mock data when API unavailable."""
    teams = [
        ("Arsenal", "Chelsea", 1.8, 1.4),
        ("Man City", "Liverpool", 2.1, 1.6),
        ("Barcelona", "Real Madrid", 1.9, 1.7),
        ("PSG", "Bayern Munich", 1.7, 1.8),
        ("Juventus", "AC Milan", 1.5, 1.3),
        ("Dortmund", "Atalanta", 1.9, 1.5),
        ("Inter", "Napoli", 1.6, 1.4),
        ("Porto", "Sporting", 1.4, 1.5),
        ("Ajax", "PSV", 1.6, 1.3),
        ("Atletico", "Sevilla", 1.5, 1.2),
        ("Benfica", "Braga", 1.7, 1.3),
        ("Roma", "Lazio", 1.6, 1.5),
    ]
    
    fixtures = []
    for home, away, home_xg, away_xg in teams:
        fixtures.append({
            "home": home,
            "away": away,
            "home_id": hash(home) % 10000,
            "away_id": hash(away) % 10000,
            "home_xg": home_xg,
            "away_xg": away_xg,
            "competition": "Mock",
        })
    
    return pd.DataFrame(fixtures)

# ══════════════════════════════════════════════════════════════════════════════
# BET SET GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def generate_flashcards(fixtures: pd.DataFrame, min_single_prob: float = 0.55) -> dict:
    """Generate flashcards for each threshold (70%, 60%, 50%, 40%)."""
    
    # Build individual bets
    all_bets = []
    for _, row in fixtures.iterrows():
        markets = calculate_markets(row["home_xg"], row["away_xg"])
        match_name = f"{row['home']} vs {row['away']}"
        
        for market, prob in markets.items():
            if prob >= min_single_prob:
                all_bets.append({
                    "match": match_name,
                    "market": market,
                    "prob": min(prob, 0.99),
                })
    
    if len(all_bets) < 3:
        return {}
    
    # Generate sets for each threshold
    thresholds = [0.70, 0.60, 0.50, 0.40]
    results = {t: [] for t in thresholds}
    
    for combo in itertools.combinations(all_bets, 3):
        # Must be 3 different matches
        if len({b["match"] for b in combo}) < 3:
            continue
        
        combined = combo[0]["prob"] * combo[1]["prob"] * combo[2]["prob"]
        
        for threshold in thresholds:
            if combined >= threshold and len(results[threshold]) < 5:
                results[threshold].append({
                    "bets": list(combo),
                    "prob": combined,
                })
    
    # Sort each threshold by probability
    for t in thresholds:
        results[t] = sorted(results[t], key=lambda x: x["prob"], reverse=True)[:5]
    
    return results

# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════

st.title("⚽ Football Betting Flashcards")
st.caption(f"📅 {date.today().strftime('%A, %B %d, %Y')}")

# Sidebar controls
use_mock = st.sidebar.checkbox("📊 Use Mock Data", value=not bool(API_KEY))
show_debug = st.sidebar.checkbox("🔍 Show Debug Info", value=False)
min_single = st.sidebar.slider("Min Individual Bet %", 50, 80, 55)

st.markdown("---")

# API setup help
if not API_KEY and not use_mock:
    st.info("""
    ### 🔑 Setup API (2 minutes, free forever)
    
    1. **Get free key:** https://www.football-data.org/client/register
    2. **Add to `.streamlit/secrets.toml`:**
       ```toml
       FOOTBALL_DATA_KEY = "your_key_here"
       ```
    3. **Restart app**
    
    Or check "Use Mock Data" in sidebar to see it working now.
    """)

# Fetch data
with st.spinner("Loading fixtures..."):
    if use_mock or not API_KEY:
        fixtures = get_mock_fixtures()
        if not use_mock:
            st.warning("💡 **Using mock data** — add FOOTBALL_DATA_KEY for live fixtures")
    else:
        fixtures = get_todays_fixtures()
        
        if fixtures.empty:
            st.warning("⚠️ No fixtures scheduled today/tomorrow. Using mock data...")
            fixtures = get_mock_fixtures()
        else:
            st.success(f"✅ Loaded {len(fixtures)} fixtures")
            
            # Calculate xG from recent form
            with st.spinner("Calculating xG from recent form..."):
                fixtures["home_xg"] = fixtures["home_id"].apply(lambda x: get_team_xg(x, home=True))
                fixtures["away_xg"] = fixtures["away_id"].apply(lambda x: get_team_xg(x, home=False))

if show_debug:
    st.subheader("🔍 Debug: Loaded Fixtures")
    st.dataframe(fixtures[["home", "away", "home_xg", "away_xg", "competition"]])

# Generate flashcards
flashcards = generate_flashcards(fixtures, min_single_prob=min_single/100)

if not flashcards or all(len(cards) == 0 for cards in flashcards.values()):
    st.error("❌ No bet sets found. Try lowering 'Min Individual Bet %' in sidebar.")
    st.stop()

# Display flashcards by threshold
threshold_config = {
    0.70: ("🟢 High Confidence", "#1eff8e"),
    0.60: ("🔵 Good Confidence", "#4da8ff"),
    0.50: ("🟡 Moderate", "#f0c55a"),
    0.40: ("🟠 Lower Confidence", "#ff8c42"),
}

for threshold, (label, color) in threshold_config.items():
    cards = flashcards.get(threshold, [])
    if not cards:
        continue
    
    st.markdown(f"### {label} (≥{threshold*100:.0f}%)")
    
    for i, card in enumerate(cards, 1):
        prob_pct = card["prob"] * 100
        
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(12, 28, 60, 0.9), rgba(10, 20, 50, 0.95));
            border: 2px solid {color}50;
            border-left: 5px solid {color};
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h4 style="color: #e8edf5; margin: 0;">Flashcard #{i}</h4>
                <div style="font-size: 28px; font-weight: bold; color: {color}; text-shadow: 0 0 10px {color}80;">
                    {prob_pct:.1f}%
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        cols = st.columns(3)
        for j, bet in enumerate(card["bets"]):
            with cols[j]:
                st.markdown(f"""
                <div style="
                    background: rgba(20, 40, 80, 0.4);
                    padding: 14px;
                    border-radius: 10px;
                    border-left: 3px solid {color};
                    margin-bottom: 10px;
                ">
                    <div style="color: #d0d8e8; font-weight: 600; margin-bottom: 6px; font-size: 13px;">
                        ⚽ {bet['match']}
                    </div>
                    <div style="color: #8899bb; font-size: 12px; margin-bottom: 6px;">
                        {bet['market']}
                    </div>
                    <div style="color: {color}; font-size: 16px; font-weight: bold;">
                        {bet['prob']*100:.1f}%
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("---")

st.caption("💡 **Probabilities from Poisson distribution based on team's recent goals scored**")
st.caption("⚠️ **For entertainment only — not financial advice**")
