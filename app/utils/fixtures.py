from datetime import datetime, timedelta
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

@st.cache_data(ttl=3600)
def get_upcoming_fixtures(days_ahead: int = 3) -> pd.DataFrame:
    fixtures = []

    for d in range(days_ahead + 1):
        date = (datetime.utcnow() + timedelta(days=d)).strftime("%Y-%m-%d")
        url = f"{BASE_URL}/fixtures/date/{date}"

        response = requests.get(url, headers=_headers(), timeout=20)
        response.raise_for_status()
        data = response.json().get("data", [])

        for m in data:
            league_id = m["league"]["id"]
            if league_id not in LEAGUES:
                continue

            fixtures.append({
                "fixture_id": m["id"],
                "date": date,
                "league": m["league"]["name"],
                "league_id": league_id,
                "home": m["localteam"]["name"],
                "away": m["visitorteam"]["name"],
                "home_id": m["localteam"]["id"],
                "away_id": m["visitorteam"]["id"]
            })

    return pd.DataFrame(fixtures)
