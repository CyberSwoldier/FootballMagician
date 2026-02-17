"""
utils/sportmonks.py
-------------------
SportMonks v3 Football API client.

Confirmed endpoints (from official docs):
  Fixtures by date : GET /v3/football/fixtures/date/{YYYY-MM-DD}
  Fixtures by team : GET /v3/football/fixtures/between/date/{from}/{to}/{team_id}
  xG data          : GET /v3/football/expected/fixtures (filter by participant)

API key must be in .streamlit/secrets.toml:
  SPORTMONKS_API_KEY = "your_token_here"
"""

import time
import logging
from datetime import date, timedelta

import requests
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
BASE_URL   = "https://api.sportmonks.com/v3/football"   # confirmed from docs
LEAGUE_IDS = {8, 11, 25, 17, 13, 73, 572, 110, 114}

MAX_RETRIES     = 3
RETRY_BACKOFF   = 2   # seconds, doubled each attempt
REQUEST_TIMEOUT = 15  # seconds per request


# ── Core HTTP helper ───────────────────────────────────────────────────────────

def _get(url: str, params: dict | None = None) -> dict:
    """
    GET request with:
      • API key injected as query param (SportMonks v3 standard)
      • Retry on 429 / 5xx with exponential backoff
      • Graceful handling of every failure mode
      • Never raises — always returns dict (empty on any error)
    """
    if params is None:
        params = {}

    # ── API key ────────────────────────────────────────────────────────────────
    try:
        params["api_token"] = st.secrets["SPORTMONKS_API_KEY"]
    except (KeyError, FileNotFoundError, Exception):
        st.error(
            "❌ SPORTMONKS_API_KEY missing from Streamlit secrets.\n"
            "Add it to `.streamlit/secrets.toml`:\n\n"
            '    SPORTMONKS_API_KEY = "your_token_here"'
        )
        return {}

    resp = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)

            # ── Rate limit ─────────────────────────────────────────────────────
            if resp.status_code == 429:
                wait = RETRY_BACKOFF ** attempt
                logger.warning("Rate limited. Waiting %ss (attempt %s/%s)", wait, attempt, MAX_RETRIES)
                time.sleep(wait)
                continue

            # ── Server error — retry ───────────────────────────────────────────
            if resp.status_code >= 500:
                wait = RETRY_BACKOFF ** attempt
                logger.warning("Server error %s. Waiting %ss (attempt %s/%s)",
                               resp.status_code, wait, attempt, MAX_RETRIES)
                time.sleep(wait)
                continue

            # ── Client error — don't retry, it won't help ──────────────────────
            if resp.status_code >= 400:
                logger.error("Client error %s for %s", resp.status_code, url)
                return {}

            # ── Guard: must be JSON ────────────────────────────────────────────
            ct = resp.headers.get("Content-Type", "")
            if "application/json" not in ct:
                logger.error("Non-JSON response (%s) from %s", ct, url)
                return {}

            payload = resp.json()

            # ── Guard: SportMonks wraps some errors as JSON with "message" ─────
            if isinstance(payload, dict) and "message" in payload and "data" not in payload:
                logger.error("API error message: %s", payload["message"])
                return {}

            return payload

        except requests.exceptions.Timeout:
            logger.warning("Timeout on attempt %s/%s for %s", attempt, MAX_RETRIES, url)
            time.sleep(RETRY_BACKOFF ** attempt)

        except requests.exceptions.ConnectionError:
            logger.warning("Connection error on attempt %s/%s for %s", attempt, MAX_RETRIES, url)
            time.sleep(RETRY_BACKOFF ** attempt)

        except requests.exceptions.RequestException as e:
            logger.error("Request exception for %s: %s", url, e)
            return {}

        except ValueError:
            logger.error("JSON decode error for %s", url)
            return {}

    logger.error("All %s retries exhausted for %s", MAX_RETRIES, url)
    return {}


def _paginate(url: str, params: dict, max_pages: int = 5) -> list:
    """Collect all pages from a paginated SportMonks endpoint."""
    results = []
    for page in range(1, max_pages + 1):
        payload = _get(url, {**params, "page": page})
        data    = payload.get("data", [])
        if not data:
            break
        results.extend(data)
        if not payload.get("pagination", {}).get("has_more", False):
            break
    return results


def _safe_float(val, fallback: float = -1.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return fallback


# ── Public API ─────────────────────────────────────────────────────────────────

def get_upcoming_fixtures() -> pd.DataFrame:
    """
    Return today's + tomorrow's fixtures for LEAGUE_IDS.

    Endpoint (confirmed):
        GET /v3/football/fixtures/date/{YYYY-MM-DD}?include=participants
    """
    EMPTY = pd.DataFrame(
        columns=["fixture_id", "home", "away", "home_id", "away_id", "league_id", "date"]
    )

    today    = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    rows     = []

    for d in [today, tomorrow]:
        # ── Confirmed URL from official SportMonks docs ────────────────────────
        records = _paginate(
            f"{BASE_URL}/fixtures/date/{d}",
            {"include": "participants"}
        )

        for m in records:
            if not isinstance(m, dict):
                continue

            league_id = m.get("league_id")
            if not isinstance(league_id, int) or league_id not in LEAGUE_IDS:
                continue

            fixture_id = m.get("id")
            if not fixture_id:
                continue

            participants = m.get("participants") or []
            if not isinstance(participants, list):
                continue

            home = next(
                (p for p in participants
                 if isinstance(p, dict)
                 and (p.get("meta") or {}).get("location") == "home"),
                None
            )
            away = next(
                (p for p in participants
                 if isinstance(p, dict)
                 and (p.get("meta") or {}).get("location") == "away"),
                None
            )

            if not home or not away:
                continue
            if not home.get("name") or not away.get("name"):
                continue
            if not home.get("id") or not away.get("id"):
                continue

            rows.append({
                "fixture_id": int(fixture_id),
                "home":       str(home["name"]),
                "away":       str(away["name"]),
                "home_id":    int(home["id"]),
                "away_id":    int(away["id"]),
                "league_id":  int(league_id),
                "date":       d,
            })

    if not rows:
        return EMPTY

    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset="fixture_id")
        .dropna(subset=["home", "away", "home_id", "away_id"])
        .reset_index(drop=True)
    )

    return df if not df.empty else EMPTY


def get_team_xg(team_id: int, home: bool = True, matches: int = 8) -> float:
    """
    Rolling average xG for a team. Never raises — always returns float.

    Priority:
      1. /v3/football/expected/fixtures  (real xG data)
      2. /v3/football/fixtures/between   (goals as proxy)
      3. Hardcoded realistic European average
    """
    # ── Guard ──────────────────────────────────────────────────────────────────
    try:
        team_id = int(team_id)
        assert team_id > 0
    except (TypeError, ValueError, AssertionError):
        return 1.35 if home else 1.05

    mult = 1.05 if home else 0.95

    # ── 1. Real xG endpoint ────────────────────────────────────────────────────
    try:
        records = _paginate(
            f"{BASE_URL}/expected/fixtures",
            {
                "filters":  f"expectedFixtureParticipants:{team_id}",
                "per_page": matches,
                "sort":     "-fixture_id",
            },
            max_pages=2,
        )
        xg_vals = []
        for row in records:
            for p in (row.get("participants") or []):
                if not isinstance(p, dict) or p.get("id") != team_id:
                    continue
                v = _safe_float((p.get("data") or {}).get("xg", p.get("xg")))
                if v >= 0:
                    xg_vals.append(v)
        if xg_vals:
            return round(sum(xg_vals) / len(xg_vals) * mult, 3)
    except Exception as e:
        logger.warning("xG endpoint error for team %s: %s", team_id, e)

    # ── 2. Goals-as-proxy fallback ─────────────────────────────────────────────
    try:
        # Confirmed endpoint: fixtures between two dates for a specific team
        today     = date.today().isoformat()
        past      = (date.today() - timedelta(days=90)).isoformat()
        records   = _paginate(
            f"{BASE_URL}/fixtures/between/date/{past}/{today}/{team_id}",
            {
                "include":  "scores;participants",
                "per_page": matches,
                "sort":     "-starting_at",
            },
            max_pages=2,
        )

        goals = []
        for g in records:
            participants = g.get("participants") or []
            scores       = g.get("scores") or []

            team_p = next(
                (p for p in participants
                 if isinstance(p, dict) and p.get("id") == team_id),
                None
            )
            if not team_p:
                continue

            location = (team_p.get("meta") or {}).get("location")
            if location not in ("home", "away"):
                continue

            for score in scores:
                if not isinstance(score, dict):
                    continue
                if score.get("description") not in ("CURRENT", "2ND_HALF", "FT"):
                    continue
                v = _safe_float((score.get("score") or {}).get(location))
                if v >= 0:
                    goals.append(v)
                break

        if goals:
            return round(sum(goals) / len(goals) * mult, 3)

    except Exception as e:
        logger.warning("Goals fallback error for team %s: %s", team_id, e)

    # ── 3. Realistic European average ─────────────────────────────────────────
    return 1.35 if home else 1.05
