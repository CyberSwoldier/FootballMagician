import itertools
from models.poisson import score_matrix

MIN_SINGLE_PROB = 0.80
MIN_SET_PROB = 0.70

def generate_sets(fixtures, model="xG Only"):
    bets = []

    for _, r in fixtures.iterrows():
        matrix = score_matrix(r.home_xg, r.away_xg)

        over_05 = sum(p for (h, a), p in matrix.items() if h + a > 0)
        under_45 = sum(p for (h, a), p in matrix.items() if h + a < 5)
        home_win = sum(p for (h, a), p in matrix.items() if h > a)
        draw = sum(p for (h, a), p in matrix.items() if h == a)
        away_win = sum(p for (h, a), p in matrix.items() if h < a)

        double_chance_home = home_win + draw
        double_chance_away = away_win + draw

        match = f"{r.home} vs {r.away}"

        markets = [
            ("Over 0.5 Goals", over_05),
            ("Under 4.5 Goals", under_45),
            ("Double Chance Home (1X)", double_chance_home),
            ("Double Chance Away (X2)", double_chance_away),
        ]

        for market, prob in markets:
            if prob >= MIN_SINGLE_PROB:
                bets.append({
                    "match": match,
                    "market": market,
                    "prob": prob,
                    "odds": 1.15 if "Over" in market else 1.18
                })

    sets = []

    for combo in itertools.combinations(bets, 3):
        matches = {b["match"] for b in combo}
        if len(matches) < 3:
            continue

        prob = combo[0]["prob"] * combo[1]["prob"] * combo[2]["prob"]
        odds = combo[0]["odds"] * combo[1]["odds"] * combo[2]["odds"]

        if prob >= MIN_SET_PROB:
            sets.append({
                "bets": combo,
                "prob": prob,
                "odds": odds
            })

    return sorted(sets, key=lambda x: x["prob"], reverse=True)
