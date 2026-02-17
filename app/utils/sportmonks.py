import requests
import pandas as pd
import streamlit as st
from datetime import date, timedelta

BASE_URL = "https://api.sportmonks.com/v3/football"

# League IDs to filter fixtures by
LEAGUE_IDS = [8, 11, 25, 17, 13, 73, 572, 110, 114]


def _get(url: str, params: dict = None) -> dict:
    """Central request helper — passes API key as query param."""
    if params is None:
        params = {}
    params["api_token"] = st.secrets["SPORTMONKS_API_KEY"]
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        st.warning(f"HTTP error {resp.status_code} for {url}: {e}")
        return {}
    except Exception as e:
        st.warning(f"Request failed for {url}: {e}")
        return {}


def get_upcoming_fixtures() -> pd.DataFrame:
    """
    Fetch today + tomorrow fixtures filtered to target leagues.
    Correct v3 endpoint: GET /v3/football/fixtures/date/{YYYY-MM-DD}
    """
    today    = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    fixtures = []

    for d in [today, tomorrow]:
        url  = f"{BASE_URL}/fixtures/date/{d}"
        data = _get(url, {"include": "participants"})

        for m in data.get("data", []):
            league_id = m.get("league_id")
            if league_id not in LEAGUE_IDS:
                continue

            participants = m.get("participants", [])
            home_team = next(
                (p for p in participants if p.get("meta", {}).get("location") == "home"), None
            )
            away_team = next(
                (p for p in participants if p.get("meta", {}).get("location") == "away"), None
            )
            if not home_team or not away_team:
                continue

            fixtures.append({
                "fixture_id": m["id"],
                "home":       home_team["name"],
                "away":       away_team["name"],
                "home_id":    home_team["id"],
                "away_id":    away_team["id"],
                "league_id":  league_id,
                "date":       d,
            })

    if not fixtures:
        return pd.DataFrame(
            columns=["fixture_id", "home", "away", "home_id", "away_id", "league_id", "date"]
        )
    return pd.DataFrame(fixtures).drop_duplicates(subset="fixture_id")


def get_team_xg(team_id: int, home: bool = True, matches: int = 8) -> float:
    """
    Rolling xG for a team. Tries the dedicated xG endpoint first,
    then falls back to goals scored from recent fixtures.
    """
    # -- Try dedicated xG endpoint (v3/football/expected/fixtures) ------------
    xg_data = _get(f"{BASE_URL}/expected/fixtures", {
        "filters":  f"expectedFixtureParticipants:{team_id}",
        "per_page": matches,
        "sort":     "-fixture_id",
    })

    xg_values = []
    for row in xg_data.get("data", []):
        for p in (row.get("participants") or []):
            if p.get("id") == team_id:
                val = (p.get("data", {}) or {}).get("xg") or p.get("xg")
                if val is not None:
                    try:
                        xg_values.append(float(val))
                    except (ValueError, TypeError):
                        pass

    if xg_values:
        avg = sum(xg_values) / len(xg_values)
        return round(avg * (1.05 if home else 0.95), 3)

    # -- Fallback: goals scored from recent fixtures --------------------------
    fix_data = _get(f"{BASE_URL}/fixtures", {
        "filters":  f"fixtureParticipants:{team_id}",
        "include":  "scores;participants",
        "per_page": matches,
        "sort":     "-starting_at",
    })

    goals_for = []
    for g in fix_data.get("data", []):
        participants = g.get("participants") or []
        scores       = g.get("scores") or []

        team_p = next((p for p in participants if p.get("id") == team_id), None)
        if not team_p:
            continue
        location = team_p.get("meta", {}).get("location")  # "home" or "away"

        for score in scores:
            if score.get("description") in ("CURRENT", "2ND_HALF", "FT"):
                score_data = score.get("score") or {}
                goals = score_data.get(location)
                if goals is not None:
                    try:
                        goals_for.append(float(goals))
                    except (ValueError, TypeError):
                        pass
                break

    if goals_for:
        avg = sum(goals_for) / len(goals_for)
        return round(avg * (1.05 if home else 0.95), 3)

    # -- Final fallback: realistic European league averages -------------------
    return 1.35 if home else 1.05
