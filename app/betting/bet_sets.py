import itertools
from models.poisson import score_matrix

# ── Thresholds ────────────────────────────────────────────────────────────────
MIN_SINGLE_PROB = 0.60   # FIX 1: was 0.80 — far too strict, filtered out almost
                          # every real bet. Over 0.5 Goals is ~95%+ but other
                          # markets like BTTS or Home Win rarely clear 80%.
MIN_SET_PROB    = 0.50   # FIX 2: was 0.70 — three legs at 0.80 each gives
                          # 0.80³ = 0.512, so sets could NEVER reach 0.70.
                          # Lowered to 0.55 so valid combos actually surface.
                          # The dashboard filter (≥70%) is applied in main.py,
                          # so you can tighten/loosen there without touching logic.

MAX_SETS        = 20     # Cap to avoid returning thousands of combos


def generate_sets(fixtures, model="xG Only"):
    """
    Build individual bets from fixture xG data, then combine into 3-leg accas.

    Each bet dict contains:
        match   str   — "Home vs Away"
        market  str   — human-readable market name
        prob    float — true probability (0–1) from Poisson model
        odds    float — estimated decimal odds (model-derived, not bookmaker)

    Each set dict contains:
        bets  list[dict] — the 3 individual bets
        prob  float      — combined probability (product of legs)
        odds  float      — combined odds (product of legs)
    """

    if fixtures.empty:
        return []

    bets = []

    for _, r in fixtures.iterrows():

        # FIX 3: Guard against missing / NaN xG values that crash score_matrix
        try:
            home_xg = float(r.home_xg)
            away_xg = float(r.away_xg)
        except (ValueError, TypeError, AttributeError):
            continue

        if home_xg <= 0 or away_xg <= 0:
            continue

        # FIX 4: Guard against score_matrix returning None or empty
        try:
            matrix = score_matrix(home_xg, away_xg)
        except Exception:
            continue

        if not matrix:
            continue

        # ── Market probabilities ──────────────────────────────────────────────

        over_05   = sum(p for (h, a), p in matrix.items() if h + a > 0)
        over_15   = sum(p for (h, a), p in matrix.items() if h + a > 1)
        over_25   = sum(p for (h, a), p in matrix.items() if h + a > 2)
        under_35  = sum(p for (h, a), p in matrix.items() if h + a < 4)
        under_45  = sum(p for (h, a), p in matrix.items() if h + a < 5)

        home_win  = sum(p for (h, a), p in matrix.items() if h > a)
        draw      = sum(p for (h, a), p in matrix.items() if h == a)
        away_win  = sum(p for (h, a), p in matrix.items() if h < a)

        double_chance_home = home_win + draw   # 1X
        double_chance_away = away_win + draw   # X2

        # FIX 5: Added BTTS — was completely missing from the original script
        btts = sum(p for (h, a), p in matrix.items() if h >= 1 and a >= 1)

        # FIX 6: Added Over 1.5 / Over 2.5 / Under 3.5 — common high-prob markets
        #        that the original script omitted entirely

        match = f"{r.home} vs {r.away}"

        # ── FIX 7: Odds are now derived from the model probability ────────────
        # Original used hardcoded 1.15/1.18 for everything, which is wrong —
        # a 95% probability event should have ~1.05 odds, not 1.15.
        # Formula: fair_odds = 1 / prob, then apply a ~5% bookmaker margin.
        # This gives realistic odds the dashboard can display meaningfully.

        def fair_odds(prob: float, margin: float = 0.05) -> float:
            """Convert true probability to decimal odds with a margin."""
            if prob <= 0:
                return 1.01
            return round((1 / prob) * (1 - margin), 3)

        markets = [
            ("Over 0.5 Goals",            over_05),
            ("Over 1.5 Goals",            over_15),
            ("Over 2.5 Goals",            over_25),
            ("Under 3.5 Goals",           under_35),
            ("Under 4.5 Goals",           under_45),
            ("Both Teams To Score",       btts),
            ("Double Chance Home (1X)",   double_chance_home),
            ("Double Chance Away (X2)",   double_chance_away),
            ("Home Win",                  home_win),
            ("Away Win",                  away_win),
            ("Draw",                      draw),
        ]

        for market, prob in markets:
            # FIX 8: Clamp probability to [0, 1] — floating-point sums from
            # the matrix can occasionally creep just above 1.0
            prob = min(max(float(prob), 0.0), 1.0)

            if prob >= MIN_SINGLE_PROB:
                bets.append({
                    "match":  match,
                    "market": market,
                    "prob":   prob,
                    "odds":   fair_odds(prob),
                })

    if not bets:
        return []

    # ── Combine into 3-leg accumulators ──────────────────────────────────────
    sets = []

    for combo in itertools.combinations(bets, 3):
        matches = {b["match"] for b in combo}

        # FIX 9: Original required len(matches) < 3 to SKIP — this is correct
        # logic but kept as-is; each leg must come from a different fixture
        if len(matches) < 3:
            continue

        # FIX 10: Also skip combos with duplicate markets on the same fixture
        # (original didn't check this — e.g. Over 0.5 + Over 1.5 on same game
        # are correlated and shouldn't both appear in the same set)
        market_match_pairs = [(b["match"], b["market"]) for b in combo]
        if len(set(market_match_pairs)) < len(market_match_pairs):
            continue

        combined_prob = combo[0]["prob"] * combo[1]["prob"] * combo[2]["prob"]
        combined_odds = combo[0]["odds"] * combo[1]["odds"] * combo[2]["odds"]

        if combined_prob >= MIN_SET_PROB:
            sets.append({
                "bets": list(combo),
                "prob": round(combined_prob, 6),
                "odds": round(combined_odds, 3),
            })

        # FIX 11: Early exit once we have enough sets — itertools.combinations
        # can generate millions of combos on large fixture lists and hang the app
        if len(sets) >= MAX_SETS * 10:
            break

    # Sort by probability descending, return top N
    sets.sort(key=lambda x: x["prob"], reverse=True)
    return sets[:MAX_SETS]
