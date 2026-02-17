import streamlit as st
from utils.sportmonks import (
    get_upcoming_fixtures,
    get_team_xg
)
from betting.bet_sets import generate_sets

st.set_page_config(layout="wide")
st.title("⚽ Football Betting Probability Engine")

# Sidebar
bankroll = st.sidebar.number_input("Bankroll (€)", 100, 20000, 1000)
model = st.sidebar.radio("Model", ["xG Only", "Market-Blended"])

# Load fixtures
fixtures = get_upcoming_fixtures()

if fixtures.empty:
    st.warning("No fixtures available for the selected competitions.")
    st.stop()

# Enrich fixtures with rolling xG
fixtures["home_xg"] = fixtures["home_id"].apply(
    lambda x: get_team_xg(x, home=True)
)
fixtures["away_xg"] = fixtures["away_id"].apply(
    lambda x: get_team_xg(x, home=False)
)

# Generate bet sets
sets = generate_sets(fixtures, model=model)

st.header("🟢 Top Safe Bet Sets (≥70%)")

# FIX 1 — User-facing message
if len(sets) == 0:
    st.warning(
        "No bet sets ≥70% probability today.\n\n"
        "This typically happens on low-fixture or high-variance days "
        "(e.g. Champions League matchdays)."
    )
    st.stop()

# Display sets
for i, s in enumerate(sets[:5]):
    st.subheader(
        f"Set #{i+1} – {s['prob']*100:.1f}% combined probability"
    )

    for b in s["bets"]:
        st.write(
            f"• {b['match']} – {b['market']} "
            f"({b['prob']*100:.1f}%)"
        )

    st.markdown(f"📊 **Total Odds:** {s['odds']:.2f}")
    st.divider()
