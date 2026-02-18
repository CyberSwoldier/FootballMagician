"""
Football Betting Probability Dashboard - FINAL
===============================================
Fixed: Real data fetching + All diverse markets visible
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

st.set_page_config(page_title="⚽ Betting Dashboard", layout="wide", initial_sidebar_state="collapsed")

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

def score_matrix(home_xg: float, away_xg: float, max_goals: int = 6) -> dict:
    matrix = {}
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            matrix[(h, a)] = poisson.pmf(h, home_xg) * poisson.pmf(a, away_xg)
    return matrix

def calculate_diverse_markets(home_xg: float, away_xg: float) -> dict:
    """Calculate ALL markets including goals, BTTS, corners, shots, fouls, cards."""
    matrix = score_matrix(home_xg, away_xg)
    total_xg = home_xg + away_xg
    
    markets = {}
    
    # ── GOALS ──────────────────────────────────────────────────────────────────
    markets["Over 0.5 Goals"] = sum(p for (h, a), p in matrix.items() if h + a > 0)
    markets["Over 1.5 Goals"] = sum(p for (h, a), p in matrix.items() if h + a > 1)
    markets["Over 2.5 Goals"] = sum(p for (h, a), p in matrix.items() if h + a > 2)
    markets["Over 3.5 Goals"] = sum(p for (h, a), p in matrix.items() if h + a > 3)
    markets["Under 2.5 Goals"] = sum(p for (h, a), p in matrix.items() if h + a < 3)
    markets["Under 3.5 Goals"] = sum(p for (h, a), p in matrix.items() if h + a < 4)
    markets["Under 4.5 Goals"] = sum(p for (h, a), p in matrix.items() if h + a < 5)
    
    # ── BTTS ───────────────────────────────────────────────────────────────────
    markets["BTTS Yes"] = sum(p for (h, a), p in matrix.items() if h >= 1 and a >= 1)
    markets["BTTS No"] = sum(p for (h, a), p in matrix.items() if h == 0 or a == 0)
    markets["BTTS & Over 2.5"] = sum(p for (h, a), p in matrix.items() if h >= 1 and a >= 1 and h + a > 2)
    
    # ── CORNERS (estimated from xG - more attacking = more corners) ───────────
    avg_corners = 10 + (total_xg - 2.5) * 1.8
    markets["Over 8.5 Corners"] = 1 - poisson.cdf(8, avg_corners)
    markets["Over 9.5 Corners"] = 1 - poisson.cdf(9, avg_corners)
    markets["Over 10.5 Corners"] = 1 - poisson.cdf(10, avg_corners)
    markets["Over 11.5 Corners"] = 1 - poisson.cdf(11, avg_corners)
    markets["Under 10.5 Corners"] = poisson.cdf(10, avg_corners)
    markets["Under 11.5 Corners"] = poisson.cdf(11, avg_corners)
    
    # ── SHOTS ON TARGET (roughly 3-4x xG per team) ────────────────────────────
    home_shots = max(3, home_xg * 3.5)
    away_shots = max(3, away_xg * 3.5)
    total_shots = home_shots + away_shots
    markets["Over 9.5 Shots on Target"] = 1 - poisson.cdf(9, total_shots)
    markets["Over 10.5 Shots on Target"] = 1 - poisson.cdf(10, total_shots)
    markets["Over 11.5 Shots on Target"] = 1 - poisson.cdf(11, total_shots)
    markets["Over 12.5 Shots on Target"] = 1 - poisson.cdf(12, total_shots)
    markets["Under 12.5 Shots on Target"] = poisson.cdf(12, total_shots)
    
    # ── FOULS (competitive matches = more fouls) ──────────────────────────────
    competitiveness = abs(home_xg - away_xg)
    avg_fouls = 22 + competitiveness * 2.5
    markets["Over 22.5 Fouls"] = 1 - poisson.cdf(22, avg_fouls)
    markets["Over 24.5 Fouls"] = 1 - poisson.cdf(24, avg_fouls)
    markets["Over 26.5 Fouls"] = 1 - poisson.cdf(26, avg_fouls)
    markets["Under 25.5 Fouls"] = poisson.cdf(25, avg_fouls)
    markets["Under 27.5 Fouls"] = poisson.cdf(27, avg_fouls)
    
    # ── CARDS (more fouls = more cards) ───────────────────────────────────────
    avg_cards = 3.5 + competitiveness * 0.8
    markets["Over 2.5 Cards"] = 1 - poisson.cdf(2, avg_cards)
    markets["Over 3.5 Cards"] = 1 - poisson.cdf(3, avg_cards)
    markets["Over 4.5 Cards"] = 1 - poisson.cdf(4, avg_cards)
    markets["Under 4.5 Cards"] = poisson.cdf(4, avg_cards)
    markets["Under 5.5 Cards"] = poisson.cdf(5, avg_cards)
    
    # ── RESULTS ────────────────────────────────────────────────────────────────
    markets["Home Win"] = sum(p for (h, a), p in matrix.items() if h > a)
    markets["Away Win"] = sum(p for (h, a), p in matrix.items() if h < a)
    markets["Draw"] = sum(p for (h, a), p in matrix.items() if h == a)
    markets["Double Chance 1X"] = sum(p for (h, a), p in matrix.items() if h >= a)
    markets["Double Chance X2"] = sum(p for (h, a), p in matrix.items() if h <= a)
    
    return markets

@st.cache_data(ttl=1800, show_spinner=False)
def get_all_fixtures() -> pd.DataFrame:
    """Fetch today's + tomorrow's fixtures from Football-Data.org API."""
    if not API_KEY:
        st.warning("⚠️ No API key found. Using mock data. Add FOOTBALL_DATA_KEY to secrets.toml for live fixtures.")
        return get_mock_fixtures()
    
    today = date.today().strftime("%Y-%m-%d")
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    all_fixtures = []
    
    st.info(f"📡 Fetching fixtures for {today} and {tomorrow}...")
    
    for league_name, comp_id in COMPETITIONS.items():
        data = api_get(f"competitions/{comp_id}/matches", {"dateFrom": today, "dateTo": tomorrow})
        
        match_count = 0
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
            match_count += 1
        
        if match_count > 0:
            st.success(f"✅ {league_name}: {match_count} fixtures")
        
        time.sleep(0.2)
    
    df = pd.DataFrame(all_fixtures)
    
    if df.empty:
        st.warning("⚠️ No fixtures found for today/tomorrow. Using mock data.")
        return get_mock_fixtures()
    
    st.success(f"✅ Total: {len(df)} fixtures loaded")
    return df

@st.cache_data(ttl=7200, show_spinner=False)
def get_team_xg(team_id: int, home: bool = True) -> float:
    """Get team's rolling xG average from last 10 matches."""
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
        avg = sum(goals_scored) / len(goals_scored)
        return round(avg * (1.05 if home else 0.95), 2)
    
    return 1.4 if home else 1.2

def get_mock_fixtures() -> pd.DataFrame:
    """Mock data for testing when API unavailable."""
    data = [
        ("Arsenal", "Chelsea", 1.8, 1.4, "Premier League"),
        ("Man City", "Liverpool", 2.1, 1.6, "Premier League"),
        ("Tottenham", "Newcastle", 1.7, 1.5, "Premier League"),
        ("Barcelona", "Real Madrid", 1.9, 1.7, "La Liga"),
        ("Atletico", "Sevilla", 1.5, 1.2, "La Liga"),
        ("Valencia", "Villarreal", 1.4, 1.3, "La Liga"),
        ("Bayern Munich", "Dortmund", 2.0, 1.5, "Bundesliga"),
        ("RB Leipzig", "Leverkusen", 1.7, 1.4, "Bundesliga"),
        ("Inter", "AC Milan", 1.6, 1.4, "Serie A"),
        ("Juventus", "Napoli", 1.5, 1.6, "Serie A"),
        ("Roma", "Lazio", 1.6, 1.5, "Serie A"),
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

def generate_all_flashcards(fixtures: pd.DataFrame) -> list:
    """Generate all bet combinations (JS filters by range)."""
    all_bets = []
    
    for _, row in fixtures.iterrows():
        markets = calculate_diverse_markets(row["home_xg"], row["away_xg"])
        match_name = f"{row['home']} vs {row['away']}"
        
        # Include bets with reasonable probability (35-95%)
        for market, prob in markets.items():
            if 0.35 <= prob <= 0.95:
                all_bets.append({
                    "match": match_name,
                    "market": market,
                    "prob": prob,
                    "league": row["league"]
                })
    
    if len(all_bets) < 3:
        return []
    
    results = []
    for combo in itertools.combinations(all_bets, 3):
        # Must be from 3 different matches
        if len({b["match"] for b in combo}) < 3:
            continue
        
        combined = combo[0]["prob"] * combo[1]["prob"] * combo[2]["prob"]
        
        if combined >= 0.35:
            results.append({"bets": list(combo), "prob": combined})
        
        if len(results) >= 300:  # Generate enough for all ranges
            break
    
    return sorted(results, key=lambda x: x["prob"], reverse=True)

# ══════════════════════════════════════════════════════════════════════════════
# LOAD DATA
# ══════════════════════════════════════════════════════════════════════════════

# Default to real data (not mock)
use_real_data = not st.sidebar.checkbox("Use Mock Data", value=False)

with st.spinner("🔄 Loading fixtures..."):
    if not use_real_data:
        st.info("📊 Using mock data (disable in sidebar for live fixtures)")
        all_fixtures = get_mock_fixtures()
    else:
        all_fixtures = get_all_fixtures()
        
        if "home_xg" not in all_fixtures.columns and not all_fixtures.empty:
            with st.spinner("🧮 Calculating xG estimates..."):
                all_fixtures["home_xg"] = all_fixtures["home_id"].apply(lambda x: get_team_xg(x, True))
                all_fixtures["away_xg"] = all_fixtures["away_id"].apply(lambda x: get_team_xg(x, False))

if all_fixtures.empty:
    st.error("❌ No fixtures available")
    st.stop()

league_counts = all_fixtures['league'].value_counts().to_dict()
all_flashcards = generate_all_flashcards(all_fixtures)

st.success(f"✅ Generated {len(all_flashcards)} bet sets from {len(all_fixtures)} fixtures")

flashcards_json = json.dumps(all_flashcards)
league_counts_json = json.dumps(league_counts)
all_leagues_json = json.dumps(list(league_counts.keys()))

html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Exo+2:wght@300;400;500;600&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root {{
  --navy-deepest: #020916; --navy-deep: #050f1e; --navy-mid: #0a1932;
  --silver-pale: #c8d4e8; --silver-bright: #e2eaf5;
  --silver-dim: #7a8ba8; --silver-muted: #4a5b78;
  --accent-cyan: #00d9ff; --accent-blue: #4da8ff; --accent-teal: #1eff8e;
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
  font-family: 'Exo 2', sans-serif;
  background: var(--navy-deepest);
  color: var(--silver-pale);
  min-height: 100vh;
}}

body::before {{
  content: '';
  position: fixed;
  inset: 0;
  background: radial-gradient(ellipse 60% 50% at 20% 20%, rgba(0, 217, 255, 0.08) 0%, transparent 60%);
  pointer-events: none;
  z-index: 0;
  animation: pulse-bg 8s ease-in-out infinite;
}}

@keyframes pulse-bg {{
  0%, 100% {{ opacity: 1; }}
  50% {{ opacity: 0.7; }}
}}

.header {{
  background: linear-gradient(135deg, rgba(5, 15, 30, 0.95), rgba(10, 25, 50, 0.92));
  border-bottom: 1px solid rgba(0, 217, 255, 0.2);
  padding: 20px 24px;
  backdrop-filter: blur(20px);
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}}

.header-top {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 16px;
}}

.brand {{
  display: flex;
  align-items: center;
  gap: 12px;
}}

.brand-icon {{
  width: 42px;
  height: 42px;
  background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  box-shadow: 0 0 25px rgba(0, 217, 255, 0.5);
}}

.brand-title {{
  font-family: 'Orbitron', sans-serif;
  font-size: 22px;
  font-weight: 900;
  letter-spacing: 2px;
  background: linear-gradient(90deg, var(--silver-bright), var(--accent-cyan));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}}

.header-stats {{
  display: flex;
  gap: 20px;
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
  font-size: 16px;
  font-weight: 700;
  color: var(--accent-cyan);
  text-shadow: 0 0 10px rgba(0, 217, 255, 0.5);
}}

.controls {{
  display: flex;
  gap: 20px;
  align-items: center;
  flex-wrap: wrap;
}}

.control-group {{
  display: flex;
  align-items: center;
  gap: 10px;
}}

.control-label {{
  font-size: 10px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--silver-muted);
  white-space: nowrap;
}}

.threshold-pills {{
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}}

.threshold-btn {{
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid rgba(0, 217, 255, 0.2);
  background: transparent;
  color: var(--silver-dim);
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}}

.threshold-btn:hover {{
  border-color: rgba(0, 217, 255, 0.5);
  color: var(--silver-bright);
}}

.threshold-btn.active {{
  background: rgba(0, 217, 255, 0.2);
  border-color: var(--accent-cyan);
  color: var(--silver-bright);
  box-shadow: 0 0 15px rgba(0, 217, 255, 0.3);
}}

.league-dropdown {{
  position: relative;
}}

.dropdown-toggle {{
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid rgba(0, 217, 255, 0.2);
  background: rgba(10, 25, 50, 0.8);
  color: var(--silver-bright);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}}

.dropdown-toggle:hover {{
  border-color: rgba(0, 217, 255, 0.5);
  background: rgba(10, 25, 50, 1);
}}

.dropdown-arrow {{
  font-size: 10px;
  transition: transform 0.2s;
}}

.dropdown-toggle.open .dropdown-arrow {{
  transform: rotate(180deg);
}}

.dropdown-menu {{
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 220px;
  background: rgba(5, 15, 30, 0.98);
  border: 1px solid rgba(0, 217, 255, 0.3);
  border-radius: 10px;
  padding: 8px;
  display: none;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.6);
  z-index: 1000;
  max-height: 350px;
  overflow-y: auto;
}}

.dropdown-menu.open {{
  display: block;
  animation: dropdown-slide 0.2s ease;
}}

@keyframes dropdown-slide {{
  from {{ opacity: 0; transform: translateY(-10px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.league-option {{
  padding: 8px 12px;
  border-radius: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 4px;
}}

.league-option:hover {{
  background: rgba(0, 217, 255, 0.1);
}}

.league-option.active {{
  background: rgba(30, 255, 142, 0.15);
  border-left: 3px solid var(--accent-teal);
  padding-left: 9px;
}}

.league-option.disabled {{
  opacity: 0.3;
  cursor: not-allowed;
}}

.league-option.disabled:hover {{
  background: transparent;
}}

.league-option-name {{
  font-size: 12px;
  color: var(--silver-pale);
}}

.league-option-count {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--accent-cyan);
  background: rgba(0, 217, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
}}

.main {{
  padding: 32px 24px;
  position: relative;
  z-index: 1;
}}

.content-subtitle {{
  font-size: 13px;
  color: var(--silver-dim);
  margin-bottom: 24px;
  letter-spacing: 0.5px;
}}

.flashcards-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 18px;
}}

.flashcard {{
  background: linear-gradient(135deg, rgba(10, 25, 50, 0.8), rgba(5, 15, 30, 0.9));
  border: 1px solid rgba(0, 217, 255, 0.2);
  border-radius: 14px;
  padding: 18px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
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
  transform: translateY(-3px);
  box-shadow: 0 10px 35px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(0, 217, 255, 0.3);
}}

.flashcard:hover::before {{
  opacity: 1;
}}

.flashcard-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(0, 217, 255, 0.1);
}}

.flashcard-id {{
  font-family: 'Orbitron', sans-serif;
  font-size: 13px;
  font-weight: 700;
  color: var(--silver-muted);
  letter-spacing: 1px;
}}

.flashcard-prob {{
  font-family: 'Orbitron', sans-serif;
  font-size: 28px;
  font-weight: 900;
  background: linear-gradient(135deg, var(--accent-cyan), var(--accent-teal));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}}

.bets-list {{
  display: flex;
  flex-direction: column;
  gap: 10px;
}}

.bet-item {{
  background: rgba(10, 25, 50, 0.6);
  border-left: 3px solid var(--accent-cyan);
  border-radius: 7px;
  padding: 10px;
  transition: all 0.2s;
}}

.bet-item:hover {{
  background: rgba(10, 25, 50, 0.9);
  border-left-color: var(--accent-teal);
  transform: translateX(3px);
}}

.bet-match {{
  font-size: 12px;
  font-weight: 600;
  color: var(--silver-bright);
  margin-bottom: 5px;
}}

.bet-market {{
  font-size: 10px;
  color: var(--silver-dim);
  margin-bottom: 5px;
}}

.bet-prob {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent-teal);
}}

.empty-state {{
  grid-column: 1 / -1;
  text-align: center;
  padding: 60px 20px;
  background: rgba(10, 25, 50, 0.5);
  border: 1px dashed rgba(0, 217, 255, 0.3);
  border-radius: 14px;
}}

.empty-icon {{
  font-size: 48px;
  margin-bottom: 14px;
  opacity: 0.5;
}}

.empty-title {{
  font-family: 'Orbitron', sans-serif;
  font-size: 20px;
  color: var(--silver-bright);
  margin-bottom: 8px;
}}

.empty-text {{
  font-size: 13px;
  color: var(--silver-dim);
  line-height: 1.6;
}}

@media (max-width: 768px) {{
  .header {{ padding: 16px; }}
  .brand-title {{ font-size: 18px; }}
  .threshold-pills {{ gap: 4px; }}
  .threshold-btn {{ padding: 6px 10px; font-size: 10px; }}
  .main {{ padding: 20px 16px; }}
  .flashcards-grid {{ grid-template-columns: 1fr; }}
}}

::-webkit-scrollbar {{ width: 5px; }}
::-webkit-scrollbar-thumb {{ background: rgba(0, 217, 255, 0.3); border-radius: 3px; }}
</style>
</head>
<body>
<div class="header">
  <div class="header-top">
    <div class="brand">
      <div class="brand-icon">⚽</div>
      <div class="brand-title">PROBABILITY ENGINE</div>
    </div>
    <div class="header-stats">
      <div class="stat-item">
        <div class="stat-label">Sets</div>
        <div class="stat-value" id="total-sets">0</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">Range</div>
        <div class="stat-value" id="range-display">40-50%</div>
      </div>
    </div>
  </div>
  
  <div class="controls">
    <div class="control-group">
      <div class="control-label">Threshold</div>
      <div class="threshold-pills">
        <button class="threshold-btn" data-min="0.70" data-max="1.00" data-range="70-100%">70-100%</button>
        <button class="threshold-btn" data-min="0.60" data-max="0.70" data-range="60-70%">60-70%</button>
        <button class="threshold-btn" data-min="0.50" data-max="0.60" data-range="50-60%">50-60%</button>
        <button class="threshold-btn active" data-min="0.40" data-max="0.50" data-range="40-50%">40-50%</button>
      </div>
    </div>
    
    <div class="league-dropdown">
      <button class="dropdown-toggle" id="league-toggle">
        <span id="league-count-text">All Leagues</span>
        <span class="dropdown-arrow">▼</span>
      </button>
      <div class="dropdown-menu" id="league-menu"></div>
    </div>
  </div>
</div>

<div class="main">
  <div class="content-subtitle" id="subtitle">Probability range: 40-50% • Diverse markets: Goals, BTTS, Corners, Shots, Fouls, Cards</div>
  <div class="flashcards-grid" id="flashcards-container"></div>
</div>

<script>
let allFlashcards = {flashcards_json};
let leagueCounts = {league_counts_json};
let selectedLeagues = {all_leagues_json};
let currentMin = 0.40;
let currentMax = 0.50;

document.addEventListener('DOMContentLoaded', () => {{
  renderLeagueDropdown();
  renderFlashcards();
  attachEventListeners();
}});

function renderLeagueDropdown() {{
  const menu = document.getElementById('league-menu');
  menu.innerHTML = '';
  
  Object.entries(leagueCounts).forEach(([league, count]) => {{
    const option = document.createElement('div');
    option.className = 'league-option';
    
    if (count === 0) {{
      option.classList.add('disabled');
    }} else if (selectedLeagues.includes(league)) {{
      option.classList.add('active');
    }}
    
    option.innerHTML = `
      <div class="league-option-name">${{league}}</div>
      <div class="league-option-count">${{count}}</div>
    `;
    
    if (count > 0) {{
      option.addEventListener('click', (e) => {{
        e.stopPropagation();
        toggleLeague(league);
      }});
    }}
    
    menu.appendChild(option);
  }});
  
  updateLeagueButtonText();
}}

function toggleLeague(league) {{
  const idx = selectedLeagues.indexOf(league);
  if (idx > -1) {{
    selectedLeagues.splice(idx, 1);
  }} else {{
    selectedLeagues.push(league);
  }}
  renderLeagueDropdown();
  renderFlashcards();
}}

function updateLeagueButtonText() {{
  const totalLeagues = Object.keys(leagueCounts).length;
  const selectedCount = selectedLeagues.length;
  const text = selectedCount === totalLeagues 
    ? 'All Leagues' 
    : `${{selectedCount}} / ${{totalLeagues}} Leagues`;
  document.getElementById('league-count-text').textContent = text;
}}

function renderFlashcards() {{
  const container = document.getElementById('flashcards-container');
  
  const filtered = allFlashcards.filter(card => {{
    if (card.prob < currentMin || card.prob >= currentMax) return false;
    const cardLeagues = card.bets.map(b => b.league);
    return cardLeagues.every(l => selectedLeagues.includes(l));
  }});
  
  document.getElementById('total-sets').textContent = filtered.length;
  
  if (filtered.length === 0) {{
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🎯</div>
        <div class="empty-title">No Sets Found</div>
        <div class="empty-text">
          No bet sets in this range for selected leagues.<br>
          Try different filters.
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

function attachEventListeners() {{
  document.querySelectorAll('.threshold-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('.threshold-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      currentMin = parseFloat(btn.dataset.min);
      currentMax = parseFloat(btn.dataset.max);
      const range = btn.dataset.range;
      
      document.getElementById('subtitle').textContent = `Probability range: ${{range}} • Diverse markets: Goals, BTTS, Corners, Shots, Fouls, Cards`;
      document.getElementById('range-display').textContent = range;
      
      renderFlashcards();
    }});
  }});
  
  const toggle = document.getElementById('league-toggle');
  const menu = document.getElementById('league-menu');
  
  toggle.addEventListener('click', (e) => {{
    e.stopPropagation();
    toggle.classList.toggle('open');
    menu.classList.toggle('open');
  }});
  
  document.addEventListener('click', () => {{
    toggle.classList.remove('open');
    menu.classList.remove('open');
  }});
}}
</script>
</body>
</html>
"""

st.components.v1.html(html_content, height=900, scrolling=True)
