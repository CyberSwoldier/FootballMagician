import requests
import pandas as pd
import streamlit as st

BASE_URL = "https://api.sportmonks.com/football/v3"

LEAGUES = [
    8,    # Premier League
    11,   # La Liga
    25,   # Bundesliga
    17,   # Serie A
    13,   # Ligue 1
    73,   # Primeira Liga
    572,  # Champions League
    110,  # Europa League
    114   # Conference League
]

def _headers():
    return {
        "Authorization": st.secrets["SPORTMONKS_API_KEY"]
    }

def get_upcoming_fixtures():
    fixtures = []

    for league in LEAGUES:
        url = f"{BASE_URL}/fixtures/upcoming/league/{league}"
        r = requests.get(url, headers=_headers()).json()

        for m in r.get("data", []):
            fixtures.append({
                "home": m["localteam"]["name"],
                "away": m["visitorteam"]["name"],
                "home_id": m["localteam"]["id"],
                "away_id": m["visitorteam"]["id"],
                "league_id": league
            })

    return pd.DataFrame(fixtures)

def get_team_xg(team_id, home=True, matches=8):
    """
    Rolling xG approximation from recent matches.
    Uses goals scored as proxy if xG endpoint unavailable.
    """
    url = f"{BASE_URL}/teams/{team_id}/fixtures"
    params = {
        "per_page": matches,
        "include": "statistics"
    }

    r = requests.get(url, headers=_headers(), params=params).json()
    games = r.get("data", [])

    goals_for = []
    goals_against = []

    for g in games:
        stats = g.get("statistics", [])
        for s in stats:
            if s["type"]["name"] == "Goals":
                if g["localteam_id"] == team_id:
                    goals_for.append(s["data"]["home"])
                    goals_against.append(s["data"]["away"])
                else:
                    goals_for.append(s["data"]["away"])
                    goals_against.append(s["data"]["home"])

    if not goals_for:
        return 1.2  # conservative fallback

    avg_for = sum(goals_for) / len(goals_for)
    avg_against = sum(goals_against) / len(goals_against)

    # Slight home/away adjustment
    if home:
        return avg_for * 1.05
    return avg_for * 0.95
