import math

def poisson(k, lam):
    return (lam ** k * math.exp(-lam)) / math.factorial(k)

def score_matrix(home_xg, away_xg, max_goals=5):
    return {
        (h, a): poisson(h, home_xg) * poisson(a, away_xg)
        for h in range(max_goals + 1)
        for a in range(max_goals + 1)
    }
