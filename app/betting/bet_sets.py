import itertools
import streamlit as st
from models.poisson import score_matrix

MIN_SINGLE_PROB = 0.30
MIN_SET_PROB    = 0.40
MAX_SETS        = 20


def generate_sets(fixtures, model="xG Only"):

    # ── CHECKPOINT 1: Did we receive any fixtures? ────────────────────────────
    st.write(f"🔍 **[DEBUG 1]** fixtures received: {len(fixtures)} rows")

    if fixtures.empty:
        st.error("❌ fixtures DataFrame is empty — get_upcoming_fixtures() returned nothing.")
        return []

    # ── CHECKPOINT 2: Do the xG columns exist and have real values? ───────────
    st.write(f"🔍 **[DEBUG 2]** columns present: `{fixtures.columns.tolist()}`")

    for col in ["home_xg", "away_xg", "home", "away"]:
        if col not in fixtures.columns:
            st.error(f"❌ Missing column: `{col}` — check get_upcoming_fixtures() and xG enrichment in main.py")
            return []

    st.dataframe(fixtures[["home", "away", "home_xg", "away_xg"]].head(10))

    # ── CHECKPOINT 3: Walk each fixture and show what the matrix produces ─────
    bets = []

    for idx, r in fixtures.iterrows():

        try:
            home_xg = float(r.home_xg)
            away_xg = float(r.away_xg)
        except (ValueError, TypeError):
            st.warning(f"⚠️ Row {idx} ({r.get('home','?')} vs {r.get('away','?')}): "
                       f"xG values not numeric — home_xg={r.home_xg!r}, away_xg={r.away_xg!r}")
            continue

        if home_xg <= 0 or away_xg <= 0:
            st.warning(f"⚠️ Row {idx} ({r.home} vs {r.away}): "
                       f"xG is zero or negative — home={home_xg}, away={away_xg}. "
                       f"get_team_xg() may be returning 0/None.")
            continue

        try:
            matrix = score_matrix(home_xg, away_xg)
        except Exception as e:
            st.error(f"❌ score_matrix() crashed for {r.home} vs {r.away} "
                     f"(xG {home_xg}/{away_xg}): {e}")
            continue

        if not matrix:
            st.warning(f"⚠️ score_matrix() returned empty dict for {r.home} vs {r.away}")
            continue

        # Compute markets
        over_05            = min(sum(p for (h, a), p in matrix.items() if h + a > 0), 1.0)
        over_15            = min(sum(p for (h, a), p in matrix.items() if h + a > 1), 1.0)
        over_25            = min(sum(p for (h, a), p in matrix.items() if h + a > 2), 1.0)
        under_35           = min(sum(p for (h, a), p in matrix.items() if h + a < 4), 1.0)
        under_45           = min(sum(p for (h, a), p in matrix.items() if h + a < 5), 1.0)
        home_win           = min(sum(p for (h, a), p in matrix.items() if h > a), 1.0)
        draw               = min(sum(p for (h, a), p in matrix.items() if h == a), 1.0)
        away_win           = min(sum(p for (h, a), p in matrix.items() if h < a), 1.0)
        double_chance_home = min(home_win + draw, 1.0)
        double_chance_away = min(away_win + draw, 1.0)
        btts               = min(sum(p for (h, a), p in matrix.items() if h >= 1 and a >= 1), 1.0)

        # ── CHECKPOINT 4: Show per-fixture market probabilities ───────────────
        st.write(f"📊 **{r.home} vs {r.away}** (xG: {home_xg:.2f} / {away_xg:.2f})")
        prob_table = {
            "Over 0.5 Goals":          f"{over_05*100:.1f}%",
            "Over 1.5 Goals":          f"{over_15*100:.1f}%",
            "Over 2.5 Goals":          f"{over_25*100:.1f}%",
            "Under 3.5 Goals":         f"{under_35*100:.1f}%",
            "Under 4.5 Goals":         f"{under_45*100:.1f}%",
            "Both Teams To Score":     f"{btts*100:.1f}%",
            "Double Chance Home (1X)": f"{double_chance_home*100:.1f}%",
            "Double Chance Away (X2)": f"{double_chance_away*100:.1f}%",
            "Home Win":                f"{home_win*100:.1f}%",
            "Away Win":                f"{away_win*100:.1f}%",
            "Draw":                    f"{draw*100:.1f}%",
        }
        st.json(prob_table)

        def fair_odds(prob: float, margin: float = 0.05) -> float:
            return round((1 / prob) * (1 - margin), 3) if prob > 0 else 1.01

        markets = [
            ("Over 0.5 Goals",           over_05),
            ("Over 1.5 Goals",           over_15),
            ("Over 2.5 Goals",           over_25),
            ("Under 3.5 Goals",          under_35),
            ("Under 4.5 Goals",          under_45),
            ("Both Teams To Score",      btts),
            ("Double Chance Home (1X)",  double_chance_home),
            ("Double Chance Away (X2)",  double_chance_away),
            ("Home Win",                 home_win),
            ("Away Win",                 away_win),
            ("Draw",                     draw),
        ]

        added = 0
        for market, prob in markets:
            if prob >= MIN_SINGLE_PROB:
                bets.append({
                    "match":  f"{r.home} vs {r.away}",
                    "market": market,
                    "prob":   prob,
                    "odds":   fair_odds(prob),
                })
                added += 1

        if added == 0:
            st.warning(f"⚠️ No market cleared {MIN_SINGLE_PROB*100:.0f}% threshold "
                       f"for {r.home} vs {r.away} — all markets below threshold.")

    # ── CHECKPOINT 5: Total bets collected ────────────────────────────────────
    st.write(f"🔍 **[DEBUG 5]** Total individual bets collected: {len(bets)}")

    if len(bets) < 3:
        st.error(f"❌ Need at least 3 bets from 3 different fixtures to form a set. "
                 f"Only {len(bets)} bets collected. "
                 f"Lower MIN_SINGLE_PROB (currently {MIN_SINGLE_PROB}) "
                 f"or check xG values.")
        return []

    # ── Combine into 3-leg accumulators ──────────────────────────────────────
    sets = []
    combos_checked = 0

    for combo in itertools.combinations(bets, 3):
        matches = {b["match"] for b in combo}
        if len(matches) < 3:
            continue

        combined_prob = combo[0]["prob"] * combo[1]["prob"] * combo[2]["prob"]
        combined_odds = combo[0]["odds"] * combo[1]["odds"] * combo[2]["odds"]

        if combined_prob >= MIN_SET_PROB:
            sets.append({
                "bets": list(combo),
                "prob": round(combined_prob, 6),
                "odds": round(combined_odds, 3),
            })

        combos_checked += 1
        if len(sets) >= MAX_SETS * 10:
            break

    # ── CHECKPOINT 6: Sets found ──────────────────────────────────────────────
    st.write(f"🔍 **[DEBUG 6]** Combos checked: {combos_checked} | "
             f"Sets above {MIN_SET_PROB*100:.0f}%: {len(sets)}")

    if not sets:
        st.error(
            f"❌ Zero sets found. Best combined prob from your bets: "
            f"{max((b['prob'] for b in bets), default=0)*100:.1f}%. "
            f"Three of those multiplied: "
            f"{max((b['prob'] for b in bets), default=0)**3*100:.1f}%. "
            f"MIN_SET_PROB is {MIN_SET_PROB*100:.0f}%."
        )

    sets.sort(key=lambda x: x["prob"], reverse=True)
    return sets[:MAX_SETS]
