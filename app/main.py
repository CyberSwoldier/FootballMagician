import streamlit as st
from utils.sportmonks import get_upcoming_fixtures
from betting.bet_sets import generate_sets

st.set_page_config(layout="wide")
st.title("⚽ Football Betting Probability Engine")

bankroll = st.sidebar.number_input("Bankroll (€)", 100, 20000, 1000)
model = st.sidebar.radio("Model", ["xG Only", "Market-Blended"])

fixtures = get_upcoming_fixtures()

sets = generate_sets(fixtures, model=model)

st.header("🟢 Top 5 Safe Bet Sets (≥70%)")

for i, s in enumerate(sets[:5]):
    st.subheader(f"Set #{i+1} – {s['prob']*100:.1f}%")
    for b in s["bets"]:
        st.write(f"• {b['match']} – {b['market']} ({b['prob']*100:.1f}%)")
    st.write(f"Total odds: {s['odds']:.2f}")
    st.divider()
