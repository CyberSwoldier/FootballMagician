import os
import requests
import pandas as pd
import streamlit as st

BASE_URL = "https://api.sportmonks.com/football/v3"

def get_upcoming_fixtures():
    api_key = st.secrets["SPORTMONKS_API_KEY"]
    headers = {"Authorization": api_key}

    leagues = [8,11,25,17,13,73,572,110,114]
    all_matches = []

    for league in leagues:
        url = f"{BASE_URL}/fixtures/upcoming/league/{league}"
        r = requests.get(url, headers=headers).json()
        for m in r.get("data", []):
            all_matches.append({
                "home": m["localteam"]["name"],
                "away": m["visitorteam"]["name"],
                "home_xg": 1.6,
                "away_xg": 1.2
            })
    return pd.DataFrame(all_matches)
