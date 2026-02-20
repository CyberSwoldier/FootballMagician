"""
Auto-Check Results Tab
======================
Automatically verify bet results via API
"""

import streamlit as st
import json
from pathlib import Path
import requests

st.set_page_config(page_title="Auto-Check Results", layout="wide")

API_KEY = st.secrets.get("FOOTBALL_DATA_KEY", "")
BASE_URL = "https://api.football-data.org/v4"
ARCHIVE_DIR = Path("bet_sets_archive")

st.title("📊 Auto-Check Bet Results")

if st.button("← Back to Main Dashboard"):
    st.switch_page("main_enhanced.py")

st.markdown("---")

def check_match_result(fixture_id: str) -> dict:
    """Fetch match result from API."""
    if not API_KEY or not fixture_id:
        return {"status": "unknown"}
    
    headers = {"X-Auth-Token": API_KEY}
    try:
        resp = requests.get(f"{BASE_URL}/matches/{fixture_id}", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            match = data if isinstance(data, dict) and "status" in data else data.get("match", data)
            
            status = match.get("status")
            if status == "FINISHED":
                score = match.get("score", {}).get("fullTime", {})
                return {
                    "status": "finished",
                    "home_score": score.get("home", 0),
                    "away_score": score.get("away", 0)
                }
        return {"status": "scheduled"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def check_bet_result(bet: dict, match_result: dict) -> bool:
    """Check if individual bet won."""
    if match_result.get("status") != "finished":
        return None
    
    home = match_result.get("home_score", 0)
    away = match_result.get("away_score", 0)
    total = home + away
    market = bet["market"]
    
    # Goals
    if "Over 0.5 Goals" in market:
        return total > 0
    elif "Over 1.5 Goals" in market:
        return total > 1
    elif "Over 2.5 Goals" in market:
        return total > 2
    elif "Under 2.5 Goals" in market:
        return total < 3
    elif "Under 3.5 Goals" in market:
        return total < 4
    
    # BTTS
    elif "BTTS" in market:
        return home >= 1 and away >= 1
    
    # Results
    elif "Home Win" in market:
        return home > away
    elif "Away Win" in market:
        return away > home
    elif "Draw" in market:
        return home == away
    elif "Double Chance 1X" in market:
        return home >= away
    elif "Double Chance X2" in market:
        return home <= away
    
    # For corners/shots/fouls - mark as unknown
    return None

def auto_check_set(bet_set: dict) -> str:
    """Check if entire set won (all 3 bets correct)."""
    results = []
    for bet in bet_set["bets"]:
        match_result = check_match_result(bet.get("match_id", ""))
        bet_result = check_bet_result(bet, match_result)
        
        if bet_result is None:
            return "pending"
        results.append(bet_result)
    
    return "correct" if all(results) else "incorrect"

def load_archive_dates() -> list:
    if not ARCHIVE_DIR.exists():
        return []
    dates = []
    for file in ARCHIVE_DIR.glob("sets_*.json"):
        date_str = file.stem.replace("sets_", "")
        dates.append(date_str)
    return sorted(dates, reverse=True)

def load_archive(date_str: str) -> dict:
    file = ARCHIVE_DIR / f"sets_{date_str}.json"
    if file.exists():
        with open(file, 'r') as f:
            return json.load(f)
    return None

def save_archive(date_str: str, data: dict):
    file = ARCHIVE_DIR / f"sets_{date_str}.json"
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

def calculate_accuracy(sets: list) -> dict:
    total = len(sets)
    correct = sum(1 for s in sets if s.get("result") == "correct")
    incorrect = sum(1 for s in sets if s.get("result") == "incorrect")
    pending = total - correct - incorrect
    accuracy = (correct / (correct + incorrect) * 100) if (correct + incorrect) > 0 else 0
    
    return {
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "pending": pending,
        "accuracy": accuracy
    }

# Main UI
archive_dates = load_archive_dates()

if not archive_dates:
    st.info("📂 No archived sets found. Save sets from the main dashboard first.")
    st.stop()

selected_date = st.selectbox("Select Date", archive_dates)

if selected_date:
    archive = load_archive(selected_date)
    
    if not archive:
        st.error("Could not load archive")
        st.stop()
    
    st.subheader(f"Sets from {selected_date}")
    
    # Auto-check button
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🔄 Auto-Check All", use_container_width=True):
            with st.spinner("Checking match results..."):
                progress_bar = st.progress(0)
                total = len(archive["sets"])
                
                for i, s in enumerate(archive["sets"]):
                    if not s.get("result") or s.get("result") == "pending":
                        result = auto_check_set(s)
                        s["result"] = result
                    progress_bar.progress((i + 1) / total)
                
                save_archive(selected_date, archive)
                st.success("✅ All results checked!")
                st.rerun()
    
    # Stats
    metrics = calculate_accuracy(archive["sets"])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Sets", metrics["total"])
    with col2:
        st.metric("🟢 Correct", metrics["correct"])
    with col3:
        st.metric("🔴 Incorrect", metrics["incorrect"])
    with col4:
        st.metric("Accuracy", f"{metrics['accuracy']:.1f}%")
    
    st.markdown("---")
    
    # Display sets
    for i, s in enumerate(archive["sets"][:30], 1):
        result = s.get("result", "pending")
        
        if result == "correct":
            icon = "🟢"
            color = "#1eff8e"
        elif result == "incorrect":
            icon = "🔴"
            color = "#ff6b35"
        else:
            icon = "⚪"
            color = "#7a8ba8"
        
        with st.expander(f"{icon} SET #{i} — {s['prob']*100:.1f}%", expanded=False):
            for bet in s["bets"]:
                st.markdown(f"**{bet['match']}**")
                st.write(f"  • {bet['market']} — {bet['prob']*100:.1f}%")
            
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Mark ✅", key=f"c_{s['set_id']}"):
                    s["result"] = "correct"
                    save_archive(selected_date, archive)
                    st.rerun()
            with col2:
                if st.button("Mark ❌", key=f"i_{s['set_id']}"):
                    s["result"] = "incorrect"
                    save_archive(selected_date, archive)
                    st.rerun()
            with col3:
                if st.button("Mark ⚪", key=f"p_{s['set_id']}"):
                    s["result"] = "pending"
                    save_archive(selected_date, archive)
                    st.rerun()
