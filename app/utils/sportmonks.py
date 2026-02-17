import requests
import pandas as pd
import streamlit as st
from datetime import date, timedelta
import time
import logging

logger = logging.getLogger(__name__)

BASE_URL   = "https://api.sportmonks.com/v3/football"
LEAGUE_IDS = {8, 11, 25, 17, 13, 73, 572, 110, 114}

# ── Request config ─────────────────────────────────────────────────────────────
MAX_RETRIES    = 3
RETRY_BACKOFF  = 2      # seconds, doubled each retry
REQUEST_TIMEOUT = 15    # seconds


def _get(url: str, params: dict = None, silent: bool = False) -> dict:
    """
    Central request helper with:
    - API key injection (query param — SportMonks v3 preferred method)
    - Automatic retry with exponential backoff on 429 / 5xx
    - Graceful handling of non-JSON responses
    - Never raises — always returns a dict (empty on failure)
    """
    if params is None:
        params = {}

    # Guard: API key missing entirely
    try:
        params["api_token"] = st.secrets["SPORTMONKS_API_KEY"]
    except (KeyError, FileNotFoundError):
        st.error("❌ SPORTMONKS_API_KEY not found in Streamlit secrets. "
                 "Add it to .streamlit/secrets.toml.")
        return {}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)

            # Rate-limited — wait and retry
            if resp.status_code == 429:
                wait = RETRY_BACKOFF ** attempt
                if not silent:
                    st.warning(f"⚠️ Rate limited by SportMonks. Retrying in {wait}s…")
                time.sleep(wait)
                continue

            # Server error — retry
            if resp.status_code >= 500:
                wait = RETRY_BACKOFF ** attempt
                if attempt < MAX_RETRIES and not silent:
                    st.warning(f"⚠️ Server error {resp.status_code}. Retry {attempt}/{MAX_RETRIES}…")
                time.sleep(wait)
                continue

            # Client error (401 unauthorised, 404 not found, etc.) — don't retry
            if resp.status_code >= 400:
                if not silent:
                    st.warning(f"⚠️ {resp.status_code} from {url} — "
                               f"check endpoint or subscription tier.")
                return {}

            # Guard: response isn't JSON (e.g. HTML error page)
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                if not silent:
                    st.warning(f"⚠️ Non-JSON response from {url} "
                               f"(Content-Type: {content_type})")
                return {}

            payload = resp.json()

            # Guard: SportMonks wraps errors in a JSON body with "message"
            if "message" in payload and "data" not in payload:
                if not silent:
                    st.warning(f"⚠️ SportMonks API error: {payload['message']}")
                return {}

            return payload

        except requests.exceptions.Timeout:
            if not silent:
                st.warning(f"⚠️ Request timed out ({REQUEST_TIMEOUT}s) for {url}. "
                           f"Retry {attempt}/{MAX_RETRIES}…")
            time.sleep(RETRY_BACKOFF ** attempt)

        except requests.exceptions.ConnectionError:
            if not silent:
                st.warning(f"⚠️ Connection error for {url}. "
                           f"Check internet / DNS. Retry {attempt}/{MAX_RETRIES}…")
            time.sleep(RETRY_BACKOFF ** attempt)

        except requests.exceptions.RequestException as e:
            if not silent:
                st.warning(f"⚠️ Unexpected request error for {url}: {e}")
            return {}

        except ValueError:
            # JSON decode failed
            if not silent:
                st.warning(f"⚠️ Could not decode JSON from {url}")
            return {}

    # All retries exhausted
    if not silent:
        st.warning(f"⚠️ All {MAX_RETRIES} retries failed for {url}")
    return {}


def _safe_float(val, fallback: float = 0.0) -> float:
    """Convert any value to float safely."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return fallback


def _paginate(url: str, params: dict, max_pages: int = 5) -> list:
    """
    Fetch all pages from a paginated SportMonks endpoint.
    Stops at max_pages to avoid runaway loops.
    """
    all_data = []
    current_url = url

    for page in range(1, max_pages + 1):
        p = {**params, "page": page}
        payload = _get(current_url, p, silent=True)
        if not payload:
            break

        data = payload.get("data", [])
        if not data:
            break

        all_data.extend(data)

        # Check if there are more pages
        pagination = payload.get("pagination", {}) or {}
        if not pagination.get("has_more", False):
            break

    return all_data


# ── Public API ─────────────────────────────────────────────────────────────────

def get_upcoming_fixtures() -> pd.DataFrame:
    """
    Fetch today + tomorrow fixtures, filtered to LEAGUE_IDS.
    Returns a DataFrame — never raises.
    """
    EMPTY = pd.DataFrame(
        columns=["fixture_id", "home", "away", "home_id", "away_id", "league_id", "date"]
    )

    today    = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    fixtures = []

    for d in [today, tomorrow]:
        url     = f"{BASE_URL}/fixtures/date/{d}"
        records = _paginate(url, {"include": "participants"})

        for m in records:
            # Guard: league filter
            league_id = m.get("league_id")
            if not isinstance(league_id, int):
                continue
            if league_id not in LEAGUE_IDS:
                continue

            # Guard: fixture must have an id
            fixture_id = m.get("id")
            if fixture_id is None:
                continue

            # Extract participants safely
            participants = m.get("participants") or []
            if not isinstance(participants, list):
                continue

            home_team = next(
                (p for p in participants
                 if isinstance(p, dict)
                 and p.get("meta", {}).get("location") == "home"),
                None
            )
            away_team = next(
                (p for p in participants
                 if isinstance(p, dict)
                 and p.get("meta", {}).get("location") == "away"),
                None
            )

            # Guard: both teams must be present with a name and id
            if not home_team or not away_team:
                continue
            if not home_team.get("name") or not away_team.get("name"):
                continue
            if not home_team.get("id") or not away_team.get("id"):
                continue

            fixtures.append({
                "fixture_id": fixture_id,
                "home":       str(home_team["name"]),
                "away":       str(away_team["name"]),
                "home_id":    int(home_team["id"]),
                "away_id":    int(away_team["id"]),
                "league_id":  int(league_id),
                "date":       d,
            })

    if not fixtures:
        return EMPTY

    df = pd.DataFrame(fixtures).drop_duplicates(subset="fixture_id")

    # Final guard: ensure required columns are not null
    required = ["home", "away", "home_id", "away_id"]
    df = df.dropna(subset=required)

    return df if not df.empty else EMPTY


def get_team_xg(team_id: int, home: bool = True, matches: int = 8) -> float:
    """
    Rolling average xG for a team. Never raises — always returns a float.

    Priority:
      1. SportMonks dedicated xG endpoint
      2. Goals scored from recent fixture scores (proxy)
      3. Hardcoded realistic European average
    """
    # Guard: team_id must be a positive integer
    try:
        team_id = int(team_id)
        assert team_id > 0
    except (TypeError, ValueError, AssertionError):
        return 1.35 if home else 1.05

    multiplier = 1.05 if home else 0.95

    # ── 1. Dedicated xG endpoint ──────────────────────────────────────────────
    try:
        xg_records = _paginate(
            f"{BASE_URL}/expected/fixtures",
            {
                "filters":  f"expectedFixtureParticipants:{team_id}",
                "per_page": matches,
                "sort":     "-fixture_id",
            },
            max_pages=2
        )

        xg_values = []
        for row in xg_records:
            for p in (row.get("participants") or []):
                if not isinstance(p, dict):
                    continue
                if p.get("id") != team_id:
                    continue
                data = p.get("data") or {}
                val  = data.get("xg") or p.get("xg")
                f    = _safe_float(val, fallback=-1)
                if f >= 0:
                    xg_values.append(f)

        if xg_values:
            avg = sum(xg_values) / len(xg_values)
            return round(avg * multiplier, 3)

    except Exception as e:
        logger.warning(f"xG endpoint failed for team {team_id}: {e}")

    # ── 2. Goals-scored fallback ──────────────────────────────────────────────
    try:
        fix_records = _paginate(
            f"{BASE_URL}/fixtures",
            {
                "filters":  f"fixtureParticipants:{team_id}",
                "include":  "scores;participants",
                "per_page": matches,
                "sort":     "-starting_at",
            },
            max_pages=2
        )

        goals_for = []
        for g in fix_records:
            participants = g.get("participants") or []
            scores       = g.get("scores") or []

            if not isinstance(participants, list) or not isinstance(scores, list):
                continue

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

                score_data = score.get("score") or {}
                goals = score_data.get(location)
                f = _safe_float(goals, fallback=-1)
                if f >= 0:
                    goals_for.append(f)
                break  # only take one score entry per fixture

        if goals_for:
            avg = sum(goals_for) / len(goals_for)
            return round(avg * multiplier, 3)

    except Exception as e:
        logger.warning(f"Goals fallback failed for team {team_id}: {e}")

    # ── 3. Hardcoded realistic fallback ──────────────────────────────────────
    return 1.35 if home else 1.05
