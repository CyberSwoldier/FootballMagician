import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date, timedelta
from scipy.stats import poisson
import itertools
import time
import streamlit.components.v1 as components

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="⚽ Betting Flashcards", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    #MainMenu, header, footer {visibility: hidden;}
    .block-container {padding-top: 1.0rem; max-width: 1400px;}
    body {
        background: radial-gradient(circle at top, #1b2740 0, #050814 55%, #02030a 100%);
        color: #e0e6f5;
    }
    h1 {color: #e5ecff;}

    /* Sidebar League Panel */
    .league-sidebar {
        background: #0b1220;
        border-right: 1px solid #2b3a5c;
        padding: 1rem 0.5rem;
        height: 100%;
    }
    .league-btn {
        display: block;
        width: 100%;
        padding: 8px 10px;
        margin-bottom: 6px;
        border-radius: 6px;
        border: 1px solid #2b3a5c;
        background: linear-gradient(135deg, #10182b, #0b1220);
        color: #d7e2ff;
        font-size: 13px;
        cursor: pointer;
        text-align: left;
        transition: all 0.15s ease-out;
    }
    .league-btn:hover {
        border-color: #4da8ff;
        box-shadow: 0 0 8px rgba(77,168,255,0.4);
    }
    .league-btn.disabled {
        opacity: 0.35;
        cursor: not-allowed;
        border-style: dashed;
    }
    .league-btn.active {
        border-color: #1eff8e;
        box-shadow: 0 0 10px rgba(30,255,142,0.5);
    }

    /* Flashcards */
    .flashcard-row {
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        margin-bottom: 18px;
    }
    .flashcard-rect {
        flex: 1 1 calc(33.333% - 16px);
        min-width: 260px;
        max-width: 380px;
        background: linear-gradient(135deg, rgba(10,20,45,0.96), rgba(5,10,25,0.98));
        border-radius: 10px;
        border: 1px solid rgba(180,190,210,0.25);
        box-shadow: 0 4px 14px rgba(0,0,0,0.45);
        padding: 14px 16px;
    }
    .flashcard-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }
    .flashcard-title {
        font-size: 14px;
        font-weight: 600;
        color: #e5ecff;
    }
    .flashcard-prob {
        font-size: 22px;
        font-weight: 700;
        text-shadow: 0 0 8px rgba(255,255,255,0.25);
    }

    /* Bets inside flashcard */
    .flashcard-bet {
        background: rgba(18,30,60,0.7);
        border-radius: 8px;
        padding: 8px 10px;
        margin-bottom: 6px;
        border-left: 3px solid rgba(180,190,210,0.6);
    }
    .flashcard-bet-match {
        font-size: 12px;
        font-weight: 600;
        color: #d7e2ff;
        margin-bottom: 3px;
    }
    .flashcard-bet-market {
        font-size: 11px;
        color: #9aa7c8;
        margin-bottom: 3px;
    }
    .flashcard-bet-prob {
        font-size: 13px;
        font-weight: 600;
    }

    /* League Stats Box */
    .league-stats-box {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(200,200,220,0.15);
        border-radius: 8px;
        padding: 8px 10px;
        margin-bottom: 10px;
        font-size: 11px;
        color: #cfd8f0;
    }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# API SETUP
# ══════════════════════════════════════════════════════════════════════════════

API_KEY = st.secrets.get("FOOTBALL_DATA_KEY", "")
BASE_URL = "https://api.football-data.org/v4"

COMPETITIONS = {
    "PL": 2021,
    "PD": 2014,
    "BL1": 2002,
    "SA": 2019,
    "FL1": 2015,
    "PPL": 2017,
    "CL": 2001,
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
        if resp.status_code != 200:
            return {}
        return resp.json()
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

@st.cache_data(ttl=1800)
def get_todays_fixtures() -> pd.DataFrame:
    if not API_KEY:
        return pd.DataFrame()
    today = date.today().strftime("%Y-%m-%d")
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    all_fixtures = []
    for comp_code, comp_id in COMPETITIONS.items():
        data = api_get(f"competitions/{comp_id}/matches", {
            "dateFrom": today,
            "dateTo": tomorrow,
        })
        for match in data.get("matches", []):
            if match.get("status") not in ["SCHEDULED", "TIMED"]:
                continue
            home = match.get("homeTeam", {})
            away = match.get("awayTeam", {})
            all_fixtures.append({
                "home": home.get("name", "Unknown"),
                "away": away.get("name", "Unknown"),
                "home_id": home.get("id", 0),
                "away_id": away.get("id", 0),
                "competition": comp_code,
            })
        time.sleep(0.2)
    return pd.DataFrame(all_fixtures)

@st.cache_data(ttl=7200)
def get_team_xg(team_id: int, home: bool = True) -> float:
    data = api_get(f"teams/{team_id}/matches", {"status": "FINISHED", "limit": 10})
    goals = []
    for match in data.get("matches", []):
        home_team = match.get("homeTeam", {})
        away_team = match.get("awayTeam", {})
        score = match.get("score", {}).get("fullTime", {})
        if home_team.get("id") == team_id:
            g = score.get("home")
        elif away_team.get("id") == team_id:
            g = score.get("away")
        else:
            g = None
        if g is not None:
            goals.append(int(g))
    if goals:
        avg = sum(goals) / len(goals)
        return round(avg * (1.05 if home else 0.95), 2)
    return 1.4 if home else 1.2

def get_mock_fixtures() -> pd.DataFrame:
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
    rows = []
    for home, away, hxg, axg in teams:
        rows.append({
            "home": home,
            "away": away,
            "home_id": hash(home) % 10000,
            "away_id": hash(away) % 10000,
            "home_xg": hxg,
            "away_xg": axg,
            "competition": "Mock",
        })
    return pd.DataFrame(rows)

# ══════════════════════════════════════════════════════════════════════════════
# FLASHCARD GENERATION (REFINED WITH LEAGUE STATS)
# ══════════════════════════════════════════════════════════════════════════════

def generate_flashcards(fixtures: pd.DataFrame, min_single_prob: float = 0.55) -> dict:
    if fixtures.empty:
        return {}

    # League stats
    league_stats = (
        fixtures.groupby("competition")
        .agg(
            avg_home_xg=("home_xg", "mean"),
            avg_away_xg=("away_xg", "mean"),
            avg_total_xg=(lambda df: (df["home_xg"] + df["away_xg"]).mean()),
            matches=("home", "count"),
        )
        .reset_index()
    )

    def scoring_profile(row):
        if row["avg_total_xg"] >= 3.0:
            return "High Scoring League"
        if row["avg_total_xg"] >= 2.3:
            return "Moderate Scoring League"
        return "Low Scoring League"

    league_stats["profile"] = league_stats.apply(scoring_profile, axis=1)
    league_stats_dict = league_stats.set_index("competition").to_dict(orient="index")

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
                    "competition": row["competition"],
                })

    if len(all_bets) < 3:
        return {}

    thresholds = [0.70, 0.60, 0.50, 0.40]
    results = {t: [] for t in thresholds}

    for combo in itertools.combinations(all_bets, 3):
        if len({b["match"] for b in combo}) < 3:
            continue

        combined = combo[0]["prob"] * combo[1]["prob"] * combo[2]["prob"]
        leagues = {b["competition"] for b in combo}
        league = leagues.pop() if len(leagues) == 1 else "Mixed"
        league_info = league_stats_dict.get(league, None)

        for t in thresholds:
            if combined >= t and len(results[t]) < 5:
                results[t].append({
                    "bets": list(combo),
                    "prob": combined,
                    "league": league,
                    "league_stats": league_info,
                })

    for t in thresholds:
        results[t] = sorted(results[t], key=lambda x: x["prob"], reverse=True)[:5]

    return results

# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════

st.title("⚽ Football Betting Flashcards")
st.caption(f"📅 {date.today().strftime('%A, %B %d, %Y')}")

left_col, right_col = st.columns([1, 3])

# Fetch fixtures
with st.spinner("Loading fixtures..."):
    use_mock = st.sidebar.checkbox("📊 Use Mock Data", value=not bool(API_KEY))
    if use_mock or not API_KEY:
        fixtures = get_mock_fixtures()
    else:
        fixtures = get_todays_fixtures()
        if fixtures.empty:
            fixtures = get_mock_fixtures()
        else:
            fixtures["home_xg"] = fixtures["home_id"].apply(lambda x: get_team_xg(x, home=True))
            fixtures["away_xg"] = fixtures["away_id"].apply(lambda x: get_team_xg(x, home=False))

# League availability
league_has_matches = {code: (fixtures["competition"] == code).any() for code in COMPETITIONS.keys()}
default_league = next((c for c, ok in league_has_matches.items() if ok), "All"

if "selected_league" not in st.session_state:
    st.session_state["selected_league"] = default_league

with left_col:
    st.markdown('<div class="league-sidebar">', unsafe_allow_html=True)

    hidden = st.text_input(
        "selected_league_hidden",
        value=st.session_state["selected_league"],
        label_visibility="hidden",
        key="league_hidden"
    )

    # Build HTML + JS safely inside one triple-quoted string
    league_html = """
    <div id="league-container">
    """

    for code in COMPETITIONS.keys():
        has = league_has_matches.get(code, False)
        classes = "league-btn"
        if not has:
            classes += " disabled"
        if code == st.session_state["selected_league"]:
            classes += " active"

        league_html += f"""
        <button class="{classes}" data-league="{code}" {'disabled' if not has else ''}>
            {code}
        </button>
        """

    league_html += """
    </div>

    <script>
    const btns = Array.from(
        document.querySelectorAll('#league-container .league-btn:not(.disabled)')
    );

    const input = window.parent.document.querySelector(
        'input[data-testid="stTextInput"][aria-label="selected_league_hidden"]'
    );

    btns.forEach(btn => {
        btn.addEventListener('click', () => {
            btns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const league = btn.getAttribute('data-league');

            if (input) {
                input.value = league;
                const event = new Event('input', { bubbles: true });
                input.dispatchEvent(event);
            }
        });
    });
    </script>
    """

    components.html(league_html, height=450, scrolling=True)

    st.markdown('</div>', unsafe_allow_html=True)
