from models.poisson import score_matrix
import itertools

def generate_sets(fixtures, model="xG Only"):
    bets = []
    for _, r in fixtures.iterrows():
        matrix = score_matrix(r.home_xg, r.away_xg)
        over05 = sum(p for (h,a),p in matrix.items() if h+a>0)
        bets.append({
            "match": f"{r.home} vs {r.away}",
            "market": "Over 0.5 Goals",
            "prob": over05,
            "odds": 1.12
        })

    sets = []
    for combo in itertools.combinations(bets, 3):
        prob = combo[0]["prob"]*combo[1]["prob"]*combo[2]["prob"]
        odds = combo[0]["odds"]*combo[1]["odds"]*combo[2]["odds"]
        if prob >= 0.70:
            sets.append({"bets": combo, "prob": prob, "odds": odds})

    return sorted(sets, key=lambda x: x["prob"], reverse=True)
