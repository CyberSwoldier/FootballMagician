"""
Football Betting Probability Dashboard
=======================================
Production-grade interactive dashboard with league filtering
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
import json

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="⚽ Betting Dashboard", layout="wide", initial_sidebar_state="collapsed")

# ══════════════════════════════════════════════════════════════════════════════
# API SETUP
# ══════════════════════════════════════════════════════════════════════════════

API_KEY = st.secrets.get("FOOTBALL_DATA_KEY", "")
BASE_URL = "https://api.football-data.org/v4"

COMPETITIONS = {
    "Premier League": 2021,
    "La Liga": 2014,
    "Bundesliga": 2002,
    "Serie A": 2019,
    "Ligue 1": 2015,
    "Primeira Liga": 2017,
    "Champions League": 2001,
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
        "Over 0.5 Goals": sum(p for (h, a), p in matrix.items() if h + a > 0),
        "Over 1.5 Goals": sum(p for (h, a), p in matrix.items() if h + a > 1),
        "Over 2.5 Goals": sum(p for (h, a), p in matrix.items() if h + a > 2),
        "Under 3.5 Goals": sum(p for (h, a), p in matrix.items() if h + a < 4),
        "BTTS": sum(p for (h, a), p in matrix.items() if h >= 1 and a >= 1),
        "Home Win": sum(p for (h, a), p in matrix.items() if h > a),
        "Away Win": sum(p for (h, a), p in matrix.items() if h < a),
        "Draw": sum(p for (h, a), p in matrix.items() if h == a),
        "Double Chance 1X": sum(p for (h, a), p in matrix.items() if h >= a),
        "Double Chance X2": sum(p for (h, a), p in matrix.items() if h <= a),
    }

# ══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800, show_spinner=False)
def get_all_fixtures() -> pd.DataFrame:
    if not API_KEY:
        return get_mock_fixtures()
    
    today = date.today().strftime("%Y-%m-%d")
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    all_fixtures = []
    
    for league_name, comp_id in COMPETITIONS.items():
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
                "league": league_name,
            })
        time.sleep(0.2)
    
    df = pd.DataFrame(all_fixtures)
    if df.empty:
        return get_mock_fixtures()
    return df

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
    data = [
        ("Arsenal", "Chelsea", 1.8, 1.4, "Premier League"),
        ("Man City", "Liverpool", 2.1, 1.6, "Premier League"),
        ("Barcelona", "Real Madrid", 1.9, 1.7, "La Liga"),
        ("Atletico", "Sevilla", 1.5, 1.2, "La Liga"),
        ("Bayern Munich", "Dortmund", 2.0, 1.5, "Bundesliga"),
        ("RB Leipzig", "Leverkusen", 1.7, 1.4, "Bundesliga"),
        ("Inter", "AC Milan", 1.6, 1.4, "Serie A"),
        ("Juventus", "Napoli", 1.5, 1.6, "Serie A"),
        ("PSG", "Lyon", 1.9, 1.3, "Ligue 1"),
        ("Marseille", "Monaco", 1.5, 1.4, "Ligue 1"),
        ("Porto", "Sporting", 1.6, 1.5, "Primeira Liga"),
        ("Benfica", "Braga", 1.8, 1.3, "Primeira Liga"),
    ]
    fixtures = []
    for home, away, home_xg, away_xg, league in data:
        fixtures.append({
            "home": home, "away": away,
            "home_id": hash(home) % 10000, "away_id": hash(away) % 10000,
            "home_xg": home_xg, "away_xg": away_xg, "league": league
        })
    return pd.DataFrame(fixtures)

# ══════════════════════════════════════════════════════════════════════════════
# BET SET GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def generate_flashcards(fixtures: pd.DataFrame, threshold: float, selected_leagues: list = None) -> list:
    # Filter by selected leagues
    if selected_leagues:
        fixtures = fixtures[fixtures['league'].isin(selected_leagues)]
    
    if fixtures.empty:
        return []
    
    # Build individual bets
    all_bets = []
    for _, row in fixtures.iterrows():
        markets = calculate_markets(row["home_xg"], row["away_xg"])
        match_name = f"{row['home']} vs {row['away']}"
        for market, prob in markets.items():
            if prob >= 0.55:
                all_bets.append({
                    "match": match_name,
                    "market": market,
                    "prob": min(prob, 0.99),
                    "league": row["league"]
                })
    
    if len(all_bets) < 3:
        return []
    
    # Generate 3-match combinations
    results = []
    for combo in itertools.combinations(all_bets, 3):
        if len({b["match"] for b in combo}) < 3:
            continue
        combined = combo[0]["prob"] * combo[1]["prob"] * combo[2]["prob"]
        if combined >= threshold:
            results.append({"bets": list(combo), "prob": combined})
        if len(results) >= 50:
            break
    
    return sorted(results, key=lambda x: x["prob"], reverse=True)[:12]

# ══════════════════════════════════════════════════════════════════════════════
# LOAD DATA
# ══════════════════════════════════════════════════════════════════════════════

use_mock = st.sidebar.checkbox("📊 Use Mock Data", value=not bool(API_KEY))

with st.spinner("Loading fixtures..."):
    if use_mock:
        all_fixtures = get_mock_fixtures()
    else:
        all_fixtures = get_all_fixtures()
        if "home_xg" not in all_fixtures.columns:
            with st.spinner("Calculating xG..."):
                all_fixtures["home_xg"] = all_fixtures["home_id"].apply(lambda x: get_team_xg(x, True))
                all_fixtures["away_xg"] = all_fixtures["away_id"].apply(lambda x: get_team_xg(x, False))

# Calculate league counts
league_counts = all_fixtures['league'].value_counts().to_dict()

# Session state for interactivity
if 'selected_threshold' not in st.session_state:
    st.session_state.selected_threshold = 0.40
if 'selected_leagues' not in st.session_state:
    st.session_state.selected_leagues = list(league_counts.keys())

# ══════════════════════════════════════════════════════════════════════════════
# HTML + CSS + JAVASCRIPT DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

# Generate flashcards data
flashcards_data = generate_flashcards(
    all_fixtures,
    st.session_state.selected_threshold,
    st.session_state.selected_leagues
)

# Convert to JSON for JavaScript
flashcards_json = json.dumps(flashcards_data)
league_counts_json = json.dumps(league_counts)
selected_leagues_json = json.dumps(st.session_state.selected_leagues)

html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Exo+2:wght@300;400;500;600&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root {{
  --navy-deepest: #020916;
  --navy-deep: #050f1e;
  --navy-mid: #0a1932;
  --navy-light: #112a4a;
  --silver-pale: #c8d4e8;
  --silver-bright: #e2eaf5;
  --silver-pure: #ffffff;
  --silver-dim: #7a8ba8;
  --silver-muted: #4a5b78;
  --accent-cyan: #00d9ff;
  --accent-blue: #4da8ff;
  --accent-teal: #1eff8e;
  --accent-gold: #ffc740;
  --accent-orange: #ff6b35;
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
  font-family: 'Exo 2', sans-serif;
  background: var(--navy-deepest);
  color: var(--silver-pale);
  overflow-x: hidden;
  min-height: 100vh;
}}

/* Animated grid background */
body::before {{
  content: '';
  position: fixed;
  inset: 0;
  background: 
    radial-gradient(ellipse 60% 50% at 20% 20%, rgba(0, 217, 255, 0.08) 0%, transparent 60%),
    radial-gradient(ellipse 50% 60% at 80% 70%, rgba(77, 168, 255, 0.06) 0%, transparent 55%);
  pointer-events: none;
  z-index: 0;
  animation: pulse-bg 8s ease-in-out infinite;
}}

@keyframes pulse-bg {{
  0%, 100% {{ opacity: 1; }}
  50% {{ opacity: 0.7; }}
}}

/* Subtle scan lines */
body::after {{
  content: '';
  position: fixed;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    rgba(0, 217, 255, 0.03) 0px,
    transparent 1px,
    transparent 2px,
    rgba(0, 217, 255, 0.03) 3px
  );
  pointer-events: none;
  z-index: 0;
  animation: scan 10s linear infinite;
}}

@keyframes scan {{
  0% {{ transform: translateY(0); }}
  100% {{ transform: translateY(20px); }}
}}

.app-container {{
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 280px 1fr;
  grid-template-rows: auto 1fr;
  min-height: 100vh;
}}

/* ===== HEADER ===== */
.header {{
  grid-column: 1 / -1;
  background: linear-gradient(135deg, rgba(5, 15, 30, 0.95), rgba(10, 25, 50, 0.92));
  border-bottom: 1px solid rgba(0, 217, 255, 0.2);
  padding: 20px 32px;
  backdrop-filter: blur(20px);
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}}

.header-brand {{
  display: flex;
  align-items: center;
  gap: 16px;
}}

.brand-icon {{
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  box-shadow: 0 0 30px rgba(0, 217, 255, 0.5);
  animation: icon-glow 3s ease-in-out infinite;
}}

@keyframes icon-glow {{
  0%, 100% {{ box-shadow: 0 0 30px rgba(0, 217, 255, 0.5); }}
  50% {{ box-shadow: 0 0 50px rgba(0, 217, 255, 0.8), 0 0 80px rgba(77, 168, 255, 0.4); }}
}}

.brand-text {{
  display: flex;
  flex-direction: column;
}}

.brand-title {{
  font-family: 'Orbitron', sans-serif;
  font-size: 26px;
  font-weight: 900;
  letter-spacing: 3px;
  background: linear-gradient(90deg, var(--silver-bright), var(--accent-cyan));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  line-height: 1;
}}

.brand-subtitle {{
  font-size: 10px;
  letter-spacing: 4px;
  text-transform: uppercase;
  color: var(--silver-dim);
  margin-top: 4px;
}}

.header-stats {{
  display: flex;
  gap: 24px;
  align-items: center;
}}

.stat-item {{
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}}

.stat-label {{
  font-size: 9px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--silver-muted);
}}

.stat-value {{
  font-family: 'Orbitron', sans-serif;
  font-size: 18px;
  font-weight: 700;
  color: var(--accent-cyan);
  text-shadow: 0 0 10px rgba(0, 217, 255, 0.5);
}}

/* ===== SIDEBAR ===== */
.sidebar {{
  background: linear-gradient(180deg, rgba(5, 15, 30, 0.9), rgba(10, 25, 50, 0.85));
  border-right: 1px solid rgba(0, 217, 255, 0.15);
  padding: 24px 16px;
  overflow-y: auto;
}}

.sidebar-section {{
  margin-bottom: 32px;
}}

.section-label {{
  font-size: 10px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: var(--silver-muted);
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}}

.section-label::after {{
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(to right, rgba(0, 217, 255, 0.3), transparent);
}}

/* Threshold selector */
.threshold-buttons {{
  display: flex;
  flex-direction: column;
  gap: 8px;
}}

.threshold-btn {{
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid rgba(0, 217, 255, 0.2);
  background: transparent;
  color: var(--silver-dim);
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}}

.threshold-btn::before {{
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(0, 217, 255, 0.1), rgba(77, 168, 255, 0.1));
  opacity: 0;
  transition: opacity 0.3s;
}}

.threshold-btn:hover {{
  border-color: rgba(0, 217, 255, 0.5);
  color: var(--silver-bright);
  transform: translateX(4px);
}}

.threshold-btn:hover::before {{
  opacity: 1;
}}

.threshold-btn.active {{
  background: linear-gradient(135deg, rgba(0, 217, 255, 0.2), rgba(77, 168, 255, 0.15));
  border-color: var(--accent-cyan);
  color: var(--silver-bright);
  box-shadow: 0 0 20px rgba(0, 217, 255, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}}

/* League selector */
.league-list {{
  display: flex;
  flex-direction: column;
  gap: 6px;
}}

.league-item {{
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid rgba(0, 217, 255, 0.15);
  background: rgba(10, 25, 50, 0.5);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  justify-content: space-between;
  align-items: center;
}}

.league-item:hover {{
  border-color: rgba(0, 217, 255, 0.4);
  background: rgba(10, 25, 50, 0.8);
  transform: translateX(2px);
}}

.league-item.active {{
  border-color: var(--accent-teal);
  background: rgba(30, 255, 142, 0.1);
  box-shadow: 0 0 15px rgba(30, 255, 142, 0.2);
}}

.league-item.disabled {{
  opacity: 0.3;
  cursor: not-allowed;
  border-color: rgba(100, 100, 100, 0.1);
}}

.league-item.disabled:hover {{
  transform: none;
  border-color: rgba(100, 100, 100, 0.1);
  background: rgba(10, 25, 50, 0.5);
}}

.league-name {{
  font-size: 12px;
  font-weight: 500;
  color: var(--silver-pale);
}}

.league-count {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  color: var(--accent-cyan);
  background: rgba(0, 217, 255, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}}

/* ===== MAIN CONTENT ===== */
.main {{
  padding: 32px;
  overflow-y: auto;
}}

.content-header {{
  margin-bottom: 28px;
}}

.content-title {{
  font-family: 'Orbitron', sans-serif;
  font-size: 28px;
  font-weight: 700;
  color: var(--silver-bright);
  margin-bottom: 8px;
  letter-spacing: 2px;
}}

.content-subtitle {{
  font-size: 13px;
  color: var(--silver-dim);
  letter-spacing: 1px;
}}

/* Flashcards grid */
.flashcards-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 20px;
  animation: fade-in 0.6s ease;
}}

@keyframes fade-in {{
  from {{ opacity: 0; transform: translateY(20px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

/* Individual flashcard */
.flashcard {{
  background: linear-gradient(135deg, rgba(10, 25, 50, 0.8), rgba(5, 15, 30, 0.9));
  border: 1px solid rgba(0, 217, 255, 0.2);
  border-radius: 16px;
  padding: 20px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
  animation: slide-up 0.5s ease both;
}}

.flashcard::before {{
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--accent-cyan), var(--accent-blue));
  opacity: 0;
  transition: opacity 0.3s;
}}

.flashcard:hover {{
  border-color: rgba(0, 217, 255, 0.5);
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(0, 217, 255, 0.3);
}}

.flashcard:hover::before {{
  opacity: 1;
}}

@keyframes slide-up {{
  from {{ opacity: 0; transform: translateY(30px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.flashcard:nth-child(1) {{ animation-delay: 0.05s; }}
.flashcard:nth-child(2) {{ animation-delay: 0.10s; }}
.flashcard:nth-child(3) {{ animation-delay: 0.15s; }}
.flashcard:nth-child(4) {{ animation-delay: 0.20s; }}
.flashcard:nth-child(5) {{ animation-delay: 0.25s; }}
.flashcard:nth-child(6) {{ animation-delay: 0.30s; }}

.flashcard-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(0, 217, 255, 0.1);
}}

.flashcard-id {{
  font-family: 'Orbitron', sans-serif;
  font-size: 14px;
  font-weight: 700;
  color: var(--silver-muted);
  letter-spacing: 1px;
}}

.flashcard-prob {{
  font-family: 'Orbitron', sans-serif;
  font-size: 32px;
  font-weight: 900;
  background: linear-gradient(135deg, var(--accent-cyan), var(--accent-teal));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 0 20px rgba(0, 217, 255, 0.5);
}}

.bets-list {{
  display: flex;
  flex-direction: column;
  gap: 12px;
}}

.bet-item {{
  background: rgba(10, 25, 50, 0.6);
  border-left: 3px solid var(--accent-cyan);
  border-radius: 8px;
  padding: 12px;
  transition: all 0.2s;
}}

.bet-item:hover {{
  background: rgba(10, 25, 50, 0.9);
  border-left-color: var(--accent-teal);
  transform: translateX(4px);
}}

.bet-match {{
  font-size: 13px;
  font-weight: 600;
  color: var(--silver-bright);
  margin-bottom: 6px;
}}

.bet-market {{
  font-size: 11px;
  color: var(--silver-dim);
  margin-bottom: 6px;
}}

.bet-prob {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  font-weight: 600;
  color: var(--accent-teal);
}}

/* Empty state */
.empty-state {{
  grid-column: 1 / -1;
  text-align: center;
  padding: 80px 20px;
  background: rgba(10, 25, 50, 0.5);
  border: 1px dashed rgba(0, 217, 255, 0.3);
  border-radius: 16px;
}}

.empty-icon {{
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}}

.empty-title {{
  font-family: 'Orbitron', sans-serif;
  font-size: 24px;
  color: var(--silver-bright);
  margin-bottom: 8px;
}}

.empty-text {{
  font-size: 14px;
  color: var(--silver-dim);
  line-height: 1.6;
}}

/* Scrollbar */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: rgba(0, 217, 255, 0.3); border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: rgba(0, 217, 255, 0.5); }}
</style>
</head>
<body>
<div class="app-container">
  <!-- HEADER -->
  <div class="header">
    <div class="header-brand">
      <div class="brand-icon">⚽</div>
      <div class="brand-text">
        <div class="brand-title">PROBABILITY</div>
        <div class="brand-subtitle">Betting Analytics Dashboard</div>
      </div>
    </div>
    <div class="header-stats">
      <div class="stat-item">
        <div class="stat-label">Total Sets</div>
        <div class="stat-value" id="total-sets">0</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">Fixtures</div>
        <div class="stat-value" id="total-fixtures">{len(all_fixtures)}</div>
      </div>
    </div>
  </div>

  <!-- SIDEBAR -->
  <div class="sidebar">
    <div class="sidebar-section">
      <div class="section-label">Threshold</div>
      <div class="threshold-buttons">
        <button class="threshold-btn" data-threshold="0.70">≥ 70%</button>
        <button class="threshold-btn" data-threshold="0.60">≥ 60%</button>
        <button class="threshold-btn" data-threshold="0.50">≥ 50%</button>
        <button class="threshold-btn active" data-threshold="0.40">≥ 40%</button>
      </div>
    </div>

    <div class="sidebar-section">
      <div class="section-label">Leagues</div>
      <div class="league-list" id="league-list">
        <!-- Generated by JS -->
      </div>
    </div>
  </div>

  <!-- MAIN CONTENT -->
  <div class="main">
    <div class="content-header">
      <div class="content-title">BET SETS</div>
      <div class="content-subtitle" id="subtitle">High-probability 3-match combinations</div>
    </div>
    <div class="flashcards-grid" id="flashcards-container">
      <!-- Generated by JS -->
    </div>
  </div>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────────
let allFlashcards = {flashcards_json};
let leagueCounts = {league_counts_json};
let selectedThreshold = {st.session_state.selected_threshold};
let selectedLeagues = {selected_leagues_json};

// ── Initialize ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {{
  renderLeagues();
  renderFlashcards();
  attachEventListeners();
}});

// ── Render leagues ─────────────────────────────────────────────────────────
function renderLeagues() {{
  const container = document.getElementById('league-list');
  container.innerHTML = '';
  
  Object.entries(leagueCounts).forEach(([league, count]) => {{
    const item = document.createElement('div');
    item.className = 'league-item';
    
    if (count === 0) {{
      item.classList.add('disabled');
    }} else if (selectedLeagues.includes(league)) {{
      item.classList.add('active');
    }}
    
    item.innerHTML = `
      <div class="league-name">${{league}}</div>
      <div class="league-count">${{count}}</div>
    `;
    
    if (count > 0) {{
      item.addEventListener('click', () => toggleLeague(league));
    }}
    
    container.appendChild(item);
  }});
}}

function toggleLeague(league) {{
  const idx = selectedLeagues.indexOf(league);
  if (idx > -1) {{
    selectedLeagues.splice(idx, 1);
  }} else {{
    selectedLeagues.push(league);
  }}
  renderLeagues();
  renderFlashcards();
}}

// ── Render flashcards ──────────────────────────────────────────────────────
function renderFlashcards() {{
  const container = document.getElementById('flashcards-container');
  
  // Filter by threshold and selected leagues
  const filtered = allFlashcards.filter(card => {{
    if (card.prob < selectedThreshold) return false;
    const cardLeagues = card.bets.map(b => b.league);
    return cardLeagues.some(l => selectedLeagues.includes(l));
  }}).slice(0, 12);
  
  document.getElementById('total-sets').textContent = filtered.length;
  
  if (filtered.length === 0) {{
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🎯</div>
        <div class="empty-title">No Sets Found</div>
        <div class="empty-text">
          No bet sets meet the current threshold and league filters.<br>
          Try lowering the threshold or selecting more leagues.
        </div>
      </div>
    `;
    return;
  }}
  
  container.innerHTML = filtered.map((card, i) => `
    <div class="flashcard">
      <div class="flashcard-header">
        <div class="flashcard-id">SET #${{String(i + 1).padStart(2, '0')}}</div>
        <div class="flashcard-prob">${{(card.prob * 100).toFixed(1)}}%</div>
      </div>
      <div class="bets-list">
        ${{card.bets.map(bet => `
          <div class="bet-item">
            <div class="bet-match">${{bet.match}}</div>
            <div class="bet-market">${{bet.market}}</div>
            <div class="bet-prob">${{(bet.prob * 100).toFixed(1)}}%</div>
          </div>
        `).join('')}}
      </div>
    </div>
  `).join('');
}}

// ── Event listeners ────────────────────────────────────────────────────────
function attachEventListeners() {{
  document.querySelectorAll('.threshold-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('.threshold-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedThreshold = parseFloat(btn.dataset.threshold);
      document.getElementById('subtitle').textContent = 
        `Combinations with ≥${{(selectedThreshold * 100).toFixed(0)}}% probability`;
      renderFlashcards();
    }});
  }});
}}
</script>
</body>
</html>
"""

# Render the dashboard
st.components.v1.html(html_content, height=900, scrolling=True)
