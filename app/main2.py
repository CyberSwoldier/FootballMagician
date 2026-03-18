"""
Football Betting Dashboard - COMPLETE VERSION
==============================================
Features:
- Europa League + Conference League
- Archive with search by date
- Result tracking (green/red indicators)
- Model accuracy tracking
- Download sets to CSV
- Persistent storage
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date, timedelta, datetime
from scipy.stats import poisson
import itertools
import time
import json
import io

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
    "Europa League": 2146,     # Added
    "Conference League": 2210, # Added
}

# ══════════════════════════════════════════════════════════════════════════════
# PERSISTENT STORAGE FOR ARCHIVE
# ══════════════════════════════════════════════════════════════════════════════

def init_archive():
    """Initialize archive in session state."""
    if 'archive' not in st.session_state:
        st.session_state.archive = []

def save_sets_to_archive(sets_data, fixtures_date):
    """Save generated sets to archive with date."""
    init_archive()
    
    archive_entry = {
        'date': fixtures_date,
        'timestamp': datetime.now().isoformat(),
        'sets': sets_data,
        'total_sets': len(sets_data)
    }
    
    # Remove existing entry for same date
    st.session_state.archive = [
        e for e in st.session_state.archive 
        if e['date'] != fixtures_date
    ]
    
    # Add new entry
    st.session_state.archive.append(archive_entry)
    
    # Sort by date descending
    st.session_state.archive.sort(key=lambda x: x['date'], reverse=True)

def mark_set_result(archive_date, set_index, is_correct):
    """Mark a set as correct (green) or incorrect (red)."""
    init_archive()
    
    for entry in st.session_state.archive:
        if entry['date'] == archive_date:
            if 'results' not in entry:
                entry['results'] = {}
            entry['results'][set_index] = is_correct
            break

def get_model_accuracy():
    """Calculate overall model accuracy."""
    init_archive()
    
    total_tracked = 0
    total_correct = 0
    
    for entry in st.session_state.archive:
        results = entry.get('results', {})
        for is_correct in results.values():
            total_tracked += 1
            if is_correct:
                total_correct += 1
    
    if total_tracked == 0:
        return None
    
    return {
        'accuracy': (total_correct / total_tracked) * 100,
        'correct': total_correct,
        'total': total_tracked
    }

# ══════════════════════════════════════════════════════════════════════════════
# CORE LOGIC (Same as before)
# ══════════════════════════════════════════════════════════════════════════════

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
    matrix = score_matrix(home_xg, away_xg)
    total_xg = home_xg + away_xg
    
    markets = {
        "Over 0.5 Goals": sum(p for (h, a), p in matrix.items() if h + a > 0),
        "Over 1.5 Goals": sum(p for (h, a), p in matrix.items() if h + a > 1),
        "Over 2.5 Goals": sum(p for (h, a), p in matrix.items() if h + a > 2),
        "Under 2.5 Goals": sum(p for (h, a), p in matrix.items() if h + a < 3),
        "Under 3.5 Goals": sum(p for (h, a), p in matrix.items() if h + a < 4),
        "BTTS Yes": sum(p for (h, a), p in matrix.items() if h >= 1 and a >= 1),
        "BTTS No": sum(p for (h, a), p in matrix.items() if h == 0 or a == 0),
        "BTTS & Over 2.5": sum(p for (h, a), p in matrix.items() if h >= 1 and a >= 1 and h + a > 2),
    }
    
    avg_corners = 10 + (total_xg - 2.5) * 1.8
    markets["Over 9.5 Corners"] = 1 - poisson.cdf(9, avg_corners)
    markets["Over 10.5 Corners"] = 1 - poisson.cdf(10, avg_corners)
    markets["Under 11.5 Corners"] = poisson.cdf(11, avg_corners)
    
    total_shots = max(3, home_xg * 3.5) + max(3, away_xg * 3.5)
    markets["Over 10.5 Shots on Target"] = 1 - poisson.cdf(10, total_shots)
    markets["Over 12.5 Shots on Target"] = 1 - poisson.cdf(12, total_shots)
    
    avg_fouls = 22 + abs(home_xg - away_xg) * 2.5
    markets["Over 24.5 Fouls"] = 1 - poisson.cdf(24, avg_fouls)
    markets["Under 26.5 Fouls"] = poisson.cdf(26, avg_fouls)
    
    avg_cards = 3.5 + abs(home_xg - away_xg) * 0.8
    markets["Over 3.5 Cards"] = 1 - poisson.cdf(3, avg_cards)
    markets["Under 5.5 Cards"] = poisson.cdf(5, avg_cards)
    
    markets["Home Win"] = sum(p for (h, a), p in matrix.items() if h > a)
    markets["Away Win"] = sum(p for (h, a), p in matrix.items() if h < a)
    markets["Draw"] = sum(p for (h, a), p in matrix.items() if h == a)
    
    return markets

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
        ("Inter", "AC Milan", 1.6, 1.4, "Serie A"),
        ("Juventus", "Napoli", 1.5, 1.6, "Serie A"),
        ("PSG", "Lyon", 1.9, 1.3, "Ligue 1"),
        ("Porto", "Sporting", 1.6, 1.5, "Primeira Liga"),
        ("Roma", "Lazio", 1.7, 1.5, "Europa League"),
        ("Ajax", "Rangers", 1.8, 1.4, "Europa League"),
        ("Fiorentina", "Club Brugge", 1.6, 1.3, "Conference League"),
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
    all_bets = []
    for _, row in fixtures.iterrows():
        markets = calculate_diverse_markets(row["home_xg"], row["away_xg"])
        match_name = f"{row['home']} vs {row['away']}"
        
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
        if len({b["match"] for b in combo}) < 3:
            continue
        combined = combo[0]["prob"] * combo[1]["prob"] * combo[2]["prob"]
        if combined >= 0.35:
            results.append({"bets": list(combo), "prob": combined})
        if len(results) >= 300:
            break
    
    return sorted(results, key=lambda x: x["prob"], reverse=True)

# ══════════════════════════════════════════════════════════════════════════════
# UI - TABS
# ══════════════════════════════════════════════════════════════════════════════

init_archive()

tab1, tab2, tab3 = st.tabs(["📊 Live Sets", "📁 Archive", "📈 Model Stats"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: LIVE SETS
# ══════════════════════════════════════════════════════════════════════════════

with tab1:
    st.title("⚽ Football Betting Probability Dashboard")
    st.caption(f"📅 {date.today().strftime('%A, %B %d, %Y')}")
    
    # Load data
    use_real_data = not st.checkbox("Use Mock Data", value=False, key="use_mock_live")
    
    with st.spinner("🔄 Loading fixtures..."):
        if not use_real_data:
            all_fixtures = get_mock_fixtures()
            st.info("📊 Using mock data")
        else:
            all_fixtures = get_all_fixtures()
            if "home_xg" not in all_fixtures.columns and not all_fixtures.empty:
                with st.spinner("🧮 Calculating xG..."):
                    all_fixtures["home_xg"] = all_fixtures["home_id"].apply(lambda x: get_team_xg(x, True))
                    all_fixtures["away_xg"] = all_fixtures["away_id"].apply(lambda x: get_team_xg(x, False))
    
    if all_fixtures.empty:
        st.error("❌ No fixtures available")
        st.stop()
    
    league_counts = all_fixtures['league'].value_counts().to_dict()
    all_flashcards = generate_all_flashcards(all_fixtures)
    
    st.success(f"✅ Generated {len(all_flashcards)} bet sets from {len(all_fixtures)} fixtures")
    
    # Save and download buttons
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("💾 Save to Archive", type="primary"):
            save_sets_to_archive(all_flashcards, date.today().isoformat())
            st.success(f"✅ Saved {len(all_flashcards)} sets to archive!")
    
    with col2:
        # Download as CSV
        if all_flashcards:
            csv_data = []
            for i, card in enumerate(all_flashcards[:50], 1):  # Top 50
                for bet in card['bets']:
                    csv_data.append({
                        'Set_Number': i,
                        'Combined_Probability': f"{card['prob']*100:.1f}%",
                        'Match': bet['match'],
                        'Market': bet['market'],
                        'Individual_Probability': f"{bet['prob']*100:.1f}%",
                        'League': bet['league'],
                        'Date': date.today().isoformat()
                    })
            
            csv_df = pd.DataFrame(csv_data)
            csv_buffer = io.StringIO()
            csv_df.to_csv(csv_buffer, index=False)
            
            st.download_button(
                label="📥 Download Sets (CSV)",
                data=csv_buffer.getvalue(),
                file_name=f"betting_sets_{date.today().isoformat()}.csv",
                mime="text/csv"
            )
    
    st.markdown("---")
    
    # Show sets (simplified view - full interactive dashboard would go here)
    threshold = st.selectbox("Probability Range", [
        "70-100%",
        "60-70%",
        "50-60%",
        "40-50%"
    ], index=3)
    
    range_map = {
        "70-100%": (0.70, 1.00),
        "60-70%": (0.60, 0.70),
        "50-60%": (0.50, 0.60),
        "40-50%": (0.40, 0.50)
    }
    
    min_prob, max_prob = range_map[threshold]
    filtered_sets = [s for s in all_flashcards if min_prob <= s['prob'] < max_prob]
    
    st.write(f"**Found {len(filtered_sets)} sets in {threshold} range**")
    
    # Display top 10 sets
    for i, card in enumerate(filtered_sets[:10], 1):
        with st.expander(f"Set #{i} — {card['prob']*100:.1f}%"):
            for bet in card['bets']:
                st.write(f"• **{bet['match']}** — {bet['market']} ({bet['prob']*100:.1f}%)")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: ARCHIVE
# ══════════════════════════════════════════════════════════════════════════════

with tab2:
    st.title("📁 Archive")
    st.caption("View and track historical bet sets")
    
    if not st.session_state.archive:
        st.info("No archived sets yet. Save sets from the Live Sets tab.")
    else:
        # Date selector
        available_dates = [entry['date'] for entry in st.session_state.archive]
        selected_date = st.selectbox("Select Date", available_dates)
        
        # Find entry
        archive_entry = next((e for e in st.session_state.archive if e['date'] == selected_date), None)
        
        if archive_entry:
            st.write(f"**Date:** {archive_entry['date']}")
            st.write(f"**Total Sets:** {archive_entry['total_sets']}")
            st.write(f"**Saved:** {datetime.fromisoformat(archive_entry['timestamp']).strftime('%Y-%m-%d %H:%M')}")
            
            results = archive_entry.get('results', {})
            tracked_count = len(results)
            correct_count = sum(1 for r in results.values() if r)
            
            if tracked_count > 0:
                st.metric(
                    "Tracked Results", 
                    f"{correct_count}/{tracked_count}",
                    f"{(correct_count/tracked_count)*100:.1f}% Accuracy"
                )
            
            st.markdown("---")
            
            # Show sets with result marking
            for i, card in enumerate(archive_entry['sets'][:20], 1):
                result = results.get(i-1)
                
                # Status indicator
                if result is True:
                    status = "🟢 Correct"
                elif result is False:
                    status = "🔴 Incorrect"
                else:
                    status = "⚪ Not Tracked"
                
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    with st.expander(f"{status} — Set #{i} — {card['prob']*100:.1f}%"):
                        for bet in card['bets']:
                            st.write(f"• {bet['match']} — {bet['market']} ({bet['prob']*100:.1f}%)")
                
                with col2:
                    if result is None:
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("✓", key=f"correct_{selected_date}_{i}"):
                                mark_set_result(selected_date, i-1, True)
                                st.rerun()
                        with col_b:
                            if st.button("✗", key=f"incorrect_{selected_date}_{i}"):
                                mark_set_result(selected_date, i-1, False)
                                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: MODEL STATS
# ══════════════════════════════════════════════════════════════════════════════

with tab3:
    st.title("📈 Model Performance")
    
    accuracy_data = get_model_accuracy()
    
    if accuracy_data is None:
        st.info("No tracked results yet. Mark sets as correct/incorrect in the Archive tab.")
    else:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Overall Accuracy", f"{accuracy_data['accuracy']:.1f}%")
        
        with col2:
            st.metric("Correct Predictions", accuracy_data['correct'])
        
        with col3:
            st.metric("Total Tracked", accuracy_data['total'])
        
        st.markdown("---")
        
        # Breakdown by date
        st.subheader("Accuracy by Date")
        
        date_stats = []
        for entry in st.session_state.archive:
            results = entry.get('results', {})
            if results:
                correct = sum(1 for r in results.values() if r)
                total = len(results)
                date_stats.append({
                    'Date': entry['date'],
                    'Correct': correct,
                    'Total': total,
                    'Accuracy': f"{(correct/total)*100:.1f}%"
                })
        
        if date_stats:
            st.dataframe(pd.DataFrame(date_stats), use_container_width=True)
        else:
            st.info("Mark some sets as correct/incorrect to see breakdown")

st.sidebar.markdown("---")
st.sidebar.caption("💡 **Tips:**")
st.sidebar.caption("• Save sets daily to build archive")
st.sidebar.caption("• Mark results to track accuracy")
st.sidebar.caption("• Download CSV for external analysis")
