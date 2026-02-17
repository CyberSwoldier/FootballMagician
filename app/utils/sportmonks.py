import requests
import pandas as pd
import streamlit as st

BASE_URL = "https://api.sportmonks.com/v3/football"  # FIX 1: URL was reversed
                                                       # was: /football/v3
                                                       # correct: /v3/football

LEAGUES = [
    8,    # Premier League
    11,   # La Liga
    25,   # Bundesliga
    17,   # Serie A
    13,   # Ligue 1
    73,   # Primeira Liga
    572,  # Champions League
    110,  # Europa League
    114,  # Conference League
]


def _headers():
    return {
        "Authorization": st.secrets["SPORTMONKS_API_KEY"]
    }


def get_upcoming_fixtures():
    fixtures = []

    for league in LEAGUES:
        url = f"{BASE_URL}/fixtures/upcoming/leagues/{league}"  # FIX 2: "league" → "leagues"
        try:
            resp = requests.get(url, headers=_headers(), timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            st.warning(f"⚠️ Could not fetch fixtures for league {league}: {e}")
            continue

        for m in data.get("data", []):

            # FIX 3: SportMonks v3 does NOT nest team data under
            # "localteam"/"visitorteam" — it uses "participants" with a
            # "meta.location" field of "home" or "away".
            # The old keys returned None silently, giving NaN team names/IDs.

            participants = m.get("participants", [])
            home_team = next(
                (p for p in participants
                 if p.get("meta", {}).get("location") == "home"),
                None
            )
            away_team = next(
                (p for p in participants
                 if p.get("meta", {}).get("location") == "away"),
                None
            )

            if not home_team or not away_team:
                continue  # skip if participant data missing

            fixtures.append({
                "home":      home_team["name"],
                "away":      away_team["name"],
                "home_id":   home_team["id"],
                "away_id":   away_team["id"],
                "league_id": league,
            })

    return pd.DataFrame(fixtures) if fixtures else pd.DataFrame(
        columns=["home", "away", "home_id", "away_id", "league_id"]
    )


def get_team_xg(team_id, home=True, matches=8):
    """
    Rolling xG approximation from recent matches.
    Uses goals scored as proxy when xG endpoint is unavailable.
    """
    url = f"{BASE_URL}/fixtures"
    params = {
        "filter[team_id]": team_id,          # FIX 4: /teams/{id}/fixtures is not
        "per_page":        matches,           # a valid v3 endpoint — use the
        "include":         "statistics",      # fixtures endpoint filtered by team
        "sort":            "-starting_at",    # newest first
    }

    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        st.warning(f"⚠️ Could not fetch fixtures for team {team_id}: {e}")
        return 1.2  # conservative fallback

    games = data.get("data", [])

    goals_for     = []
    goals_against = []

    for g in games:
        stats = g.get("statistics", [])

        # FIX 5: Statistics in v3 are a list of dicts with "type_id" not
        # nested under "type"/"name". Goals type_id = 52.
        # Also added a fallback that checks both the old and new structure
        # so it works regardless of which include format SportMonks returns.

        for s in stats:
            # Try v3 structure first (type_id)
            type_id   = s.get("type_id")
            type_name = s.get("type", {}).get("name", "") if isinstance(s.get("type"), dict) else ""

            is_goals = (type_id == 52) or (type_name == "Goals")
            if not is_goals:
                continue

            # FIX 6: v3 uses "participant_id" not "localteam_id"
            # Determine home/away from participants on the fixture
            participants = g.get("participants", [])
            home_p = next(
                (p for p in participants
                 if p.get("meta", {}).get("location") == "home"),
                None
            )

            detail = s.get("data", {}) or {}
            home_val = detail.get("home") if detail.get("home") is not None else s.get("value", {}).get("home")
            away_val = detail.get("away") if detail.get("away") is not None else s.get("value", {}).get("away")

            if home_val is None or away_val is None:
                continue

            try:
                home_goals = float(home_val)
                away_goals = float(away_val)
            except (TypeError, ValueError):
                continue

            if home_p and home_p["id"] == team_id:
                goals_for.append(home_goals)
                goals_against.append(away_goals)
            else:
                goals_for.append(away_goals)
                goals_against.append(home_goals)

    if not goals_for:
        return 1.2  # conservative fallback if no stats found

    avg_for = sum(goals_for) / len(goals_for)

    # Home/away adjustment
    return round(avg_for * 1.05, 3) if home else round(avg_for * 0.95, 3)
