import streamlit as st
from utils.sportmonks import get_upcoming_fixtures, get_team_xg
from betting.bet_sets import generate_sets
import json

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Football Betting Probability Engine",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Hide Streamlit chrome so the custom UI takes over fully ───────────────────
st.markdown("""
<style>
    #MainMenu, header, footer { visibility: hidden; }
    .block-container { padding: 0 !important; max-width: 100% !important; }
    [data-testid="stAppViewContainer"] { padding: 0 !important; }
    [data-testid="stSidebar"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ── Load & enrich fixtures ─────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_fixtures():
    fixtures = get_upcoming_fixtures()
    if fixtures.empty:
        return fixtures
    fixtures["home_xg"] = fixtures["home_id"].apply(
        lambda x: get_team_xg(x, home=True)
    )
    fixtures["away_xg"] = fixtures["away_id"].apply(
        lambda x: get_team_xg(x, home=False)
    )
    return fixtures

@st.cache_data(ttl=300, show_spinner=False)
def load_sets(model: str):
    fixtures = load_fixtures()
    if fixtures.empty:
        return []
    return generate_sets(fixtures, model=model)

# ── Sidebar controls (hidden from view but values read by Python) ──────────────
bankroll = st.sidebar.number_input("Bankroll (€)", 100, 20000, 1000, step=50)
model    = st.sidebar.radio("Model", ["xG Only", "Market-Blended"])

# ── Fetch sets & serialise for JS ─────────────────────────────────────────────
raw_sets = load_sets(model)
no_data  = len(raw_sets) == 0

# Convert to JSON-safe list for injection into JS
sets_json = json.dumps([
    {
        "prob":  float(s["prob"]),
        "odds":  float(s["odds"]),
        "bets": [
            {
                "match":  b["match"],
                "market": b["market"],
                "prob":   float(b["prob"]),
            }
            for b in s["bets"]
        ],
    }
    for s in raw_sets
])

# ── Full HTML dashboard ────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Football Betting Probability Engine</title>
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --navy-deepest: #040d1a;
      --navy-deep: #071428;
      --navy-mid: #0a1f40;
      --navy-light: #122b55;
      --navy-accent: #1a3a70;
      --silver-pale: #d0d8e8;
      --silver-bright: #e8edf5;
      --silver-shine: #f2f5fa;
      --silver-pure: #ffffff;
      --silver-dim: #8899bb;
      --silver-muted: #4a5a78;
      --gold-accent: #c9a84c;
      --gold-glow: #f0c55a;
      --green-safe: #1eff8e;
      --green-dim: #0fa855;
      --red-risk: #ff4566;
      --blue-highlight: #4da8ff;
      --card-bg: rgba(12, 28, 60, 0.85);
      --card-border: rgba(180, 210, 255, 0.1);
    }}

    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'DM Sans', sans-serif;
      background: var(--navy-deepest);
      color: var(--silver-pale);
      min-height: 900px;
      overflow-x: hidden;
    }}

    body::before {{
      content: '';
      position: fixed;
      inset: 0;
      background:
        radial-gradient(ellipse 80% 60% at 15% 10%, rgba(20, 60, 140, 0.4) 0%, transparent 60%),
        radial-gradient(ellipse 60% 50% at 85% 80%, rgba(10, 35, 90, 0.5) 0%, transparent 55%),
        radial-gradient(ellipse 40% 40% at 50% 50%, rgba(5, 15, 40, 0.9) 0%, transparent 100%);
      pointer-events: none;
      z-index: 0;
    }}

    body::after {{
      content: '';
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(rgba(100, 150, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(100, 150, 255, 0.03) 1px, transparent 1px);
      background-size: 40px 40px;
      pointer-events: none;
      z-index: 0;
    }}

    .app-shell {{
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: 280px 1fr;
      grid-template-rows: 72px 1fr;
      min-height: 900px;
    }}

    /* HEADER */
    .header {{
      grid-column: 1 / -1;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 32px;
      background: rgba(4, 13, 26, 0.95);
      border-bottom: 1px solid rgba(100, 160, 255, 0.12);
      backdrop-filter: blur(20px);
      position: sticky;
      top: 0;
      z-index: 100;
    }}

    .header-brand {{ display: flex; align-items: center; gap: 14px; }}

    .brand-icon {{
      width: 38px; height: 38px;
      background: linear-gradient(135deg, var(--navy-accent), var(--blue-highlight));
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 20px;
      box-shadow: 0 0 20px rgba(77, 168, 255, 0.35);
      animation: icon-pulse 3s ease-in-out infinite;
    }}

    @keyframes icon-pulse {{
      0%, 100% {{ box-shadow: 0 0 20px rgba(77, 168, 255, 0.35); }}
      50%       {{ box-shadow: 0 0 35px rgba(77, 168, 255, 0.6); }}
    }}

    .brand-name {{
      font-family: 'Bebas Neue', sans-serif;
      font-size: 22px; letter-spacing: 2px;
      color: var(--silver-bright); line-height: 1;
    }}

    .brand-sub {{
      font-size: 10px; letter-spacing: 3px;
      color: var(--silver-dim); text-transform: uppercase; margin-top: 2px;
    }}

    .header-status {{
      display: flex; align-items: center; gap: 8px;
      font-size: 12px; color: var(--silver-dim);
      letter-spacing: 1px; text-transform: uppercase;
    }}

    .status-dot {{
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--green-safe);
      box-shadow: 0 0 8px var(--green-safe);
      animation: blink 2s ease-in-out infinite;
    }}

    @keyframes blink {{
      0%, 100% {{ opacity: 1; }}
      50%       {{ opacity: 0.3; }}
    }}

    .header-time {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px; color: var(--silver-dim);
    }}

    /* SIDEBAR */
    .sidebar {{
      background: rgba(7, 20, 40, 0.9);
      border-right: 1px solid rgba(100, 160, 255, 0.1);
      padding: 28px 20px;
      overflow-y: auto;
      display: flex; flex-direction: column; gap: 28px;
    }}

    .sidebar-section-label {{
      font-size: 10px; letter-spacing: 3px;
      text-transform: uppercase; color: var(--silver-muted);
      margin-bottom: 12px;
      display: flex; align-items: center; gap: 8px;
    }}

    .sidebar-section-label::after {{
      content: ''; flex: 1; height: 1px;
      background: rgba(100, 160, 255, 0.12);
    }}

    .bankroll-card {{
      background: linear-gradient(135deg, rgba(26, 58, 112, 0.6), rgba(10, 31, 64, 0.8));
      border: 1px solid rgba(100, 160, 255, 0.18);
      border-radius: 14px; padding: 20px 18px;
      position: relative; overflow: hidden;
    }}

    .bankroll-card::before {{
      content: '';
      position: absolute; top: -30px; right: -30px;
      width: 100px; height: 100px;
      background: radial-gradient(circle, rgba(77, 168, 255, 0.15), transparent 70%);
      pointer-events: none;
    }}

    .bankroll-label {{
      font-size: 10px; letter-spacing: 2.5px;
      text-transform: uppercase; color: var(--silver-muted); margin-bottom: 8px;
    }}

    .bankroll-value {{
      font-family: 'Bebas Neue', sans-serif;
      font-size: 42px; letter-spacing: 1px;
      color: var(--silver-shine); line-height: 1;
    }}

    .bankroll-currency {{
      font-size: 20px; color: var(--gold-accent);
      vertical-align: super;
      font-family: 'DM Sans', sans-serif; font-weight: 300;
    }}

    .bankroll-slider-wrapper {{ margin-top: 14px; }}

    input[type="range"] {{
      -webkit-appearance: none;
      width: 100%; height: 4px; border-radius: 2px;
      background: linear-gradient(to right,
        var(--blue-highlight) 0%,
        var(--blue-highlight) var(--progress, 5%),
        rgba(100,150,255,0.2) var(--progress, 5%));
      outline: none; cursor: pointer;
    }}

    input[type="range"]::-webkit-slider-thumb {{
      -webkit-appearance: none;
      width: 16px; height: 16px; border-radius: 50%;
      background: var(--silver-bright);
      box-shadow: 0 0 10px rgba(77, 168, 255, 0.6);
      cursor: pointer; transition: box-shadow 0.2s;
    }}

    input[type="range"]::-webkit-slider-thumb:hover {{
      box-shadow: 0 0 18px rgba(77, 168, 255, 0.9);
    }}

    .bankroll-range-labels {{
      display: flex; justify-content: space-between;
      font-size: 10px; color: var(--silver-muted);
      margin-top: 6px;
      font-family: 'JetBrains Mono', monospace;
    }}

    .model-pills {{ display: flex; flex-direction: column; gap: 8px; }}

    .model-pill {{
      padding: 12px 16px; border-radius: 10px;
      border: 1px solid rgba(100, 160, 255, 0.14);
      background: transparent; color: var(--silver-dim);
      font-family: 'DM Sans', sans-serif;
      font-size: 13px; font-weight: 500;
      cursor: pointer; transition: all 0.25s ease;
      text-align: left; display: flex; align-items: center; gap: 10px;
    }}

    .model-pill:hover {{
      background: rgba(30, 60, 120, 0.4);
      border-color: rgba(100, 160, 255, 0.3);
      color: var(--silver-bright);
    }}

    .model-pill.active {{
      background: linear-gradient(135deg, rgba(30, 80, 180, 0.5), rgba(20, 50, 120, 0.6));
      border-color: rgba(77, 168, 255, 0.5);
      color: var(--silver-shine);
      box-shadow: 0 0 20px rgba(30, 80, 180, 0.3), inset 0 1px 0 rgba(255,255,255,0.08);
    }}

    .pill-dot {{
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--silver-muted);
      transition: all 0.25s; flex-shrink: 0;
    }}

    .model-pill.active .pill-dot {{
      background: var(--blue-highlight);
      box-shadow: 0 0 8px var(--blue-highlight);
    }}

    .sidebar-stats {{ display: flex; flex-direction: column; gap: 10px; }}

    .stat-row {{
      display: flex; justify-content: space-between; align-items: center;
      padding: 10px 14px;
      background: rgba(10, 20, 45, 0.6);
      border-radius: 8px;
      border: 1px solid rgba(100, 160, 255, 0.07);
    }}

    .stat-name {{ font-size: 11px; color: var(--silver-muted); letter-spacing: 0.5px; }}

    .stat-val {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px; font-weight: 600; color: var(--silver-bright);
    }}

    .stat-val.good {{ color: var(--green-safe); }}
    .stat-val.warn {{ color: var(--gold-accent); }}

    /* MAIN */
    .main {{
      padding: 32px 36px;
      overflow-y: auto;
      display: flex; flex-direction: column; gap: 28px;
    }}

    .page-header {{
      display: flex; align-items: flex-end; justify-content: space-between;
    }}

    .page-title {{
      font-family: 'Bebas Neue', sans-serif;
      font-size: 48px; letter-spacing: 3px;
      color: var(--silver-shine); line-height: 1;
    }}

    .page-title span {{ color: var(--blue-highlight); }}

    .page-subtitle {{
      font-size: 13px; color: var(--silver-muted);
      letter-spacing: 1px; margin-top: 4px;
    }}

    .refresh-btn {{
      padding: 10px 20px; border-radius: 8px;
      border: 1px solid rgba(77, 168, 255, 0.35);
      background: rgba(20, 50, 110, 0.3);
      color: var(--blue-highlight);
      font-family: 'DM Sans', sans-serif;
      font-size: 13px; font-weight: 500; cursor: pointer;
      transition: all 0.2s;
      display: flex; align-items: center; gap: 8px;
    }}

    .refresh-btn:hover {{
      background: rgba(20, 50, 110, 0.6);
      border-color: var(--blue-highlight);
      box-shadow: 0 0 16px rgba(77, 168, 255, 0.2);
    }}

    .filter-bar {{
      display: flex; align-items: center; gap: 16px;
      padding: 14px 20px;
      background: rgba(10, 25, 55, 0.7);
      border: 1px solid rgba(100, 160, 255, 0.1);
      border-radius: 12px;
      backdrop-filter: blur(10px);
    }}

    .filter-label {{
      font-size: 11px; letter-spacing: 2px;
      text-transform: uppercase; color: var(--silver-muted); white-space: nowrap;
    }}

    .threshold-pills {{ display: flex; gap: 8px; }}

    .thr-pill {{
      padding: 6px 14px; border-radius: 20px;
      font-size: 12px; font-weight: 500;
      border: 1px solid rgba(100, 160, 255, 0.18);
      background: transparent; color: var(--silver-dim);
      cursor: pointer; transition: all 0.2s;
      font-family: 'JetBrains Mono', monospace;
    }}

    .thr-pill:hover {{
      border-color: rgba(100, 160, 255, 0.4); color: var(--silver-bright);
    }}

    .thr-pill.active {{
      background: rgba(30, 130, 80, 0.3);
      border-color: var(--green-safe); color: var(--green-safe);
    }}

    .filter-divider {{ width: 1px; height: 24px; background: rgba(100, 160, 255, 0.12); }}

    .sets-count-badge {{
      margin-left: auto; display: flex; align-items: center; gap: 8px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px; color: var(--silver-dim);
    }}

    .count-num {{ font-size: 18px; font-weight: 600; color: var(--green-safe); }}

    .section-heading {{
      display: flex; align-items: center; gap: 12px;
      font-family: 'Bebas Neue', sans-serif;
      font-size: 22px; letter-spacing: 2px; color: var(--silver-bright);
    }}

    .heading-badge {{
      display: inline-flex; align-items: center; gap: 5px;
      padding: 4px 10px; border-radius: 20px;
      background: rgba(30, 130, 80, 0.2);
      border: 1px solid rgba(30, 255, 142, 0.3);
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px; font-weight: 600;
      color: var(--green-safe); letter-spacing: 1px;
    }}

    .sets-grid {{ display: flex; flex-direction: column; gap: 18px; }}

    .bet-set-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px; overflow: hidden;
      position: relative;
      transition: transform 0.25s ease, box-shadow 0.25s ease;
      animation: slide-in 0.4s ease both;
    }}

    @keyframes slide-in {{
      from {{ opacity: 0; transform: translateY(16px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}

    .bet-set-card:nth-child(1) {{ animation-delay: 0.05s; }}
    .bet-set-card:nth-child(2) {{ animation-delay: 0.10s; }}
    .bet-set-card:nth-child(3) {{ animation-delay: 0.15s; }}
    .bet-set-card:nth-child(4) {{ animation-delay: 0.20s; }}
    .bet-set-card:nth-child(5) {{ animation-delay: 0.25s; }}

    .bet-set-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 12px 40px rgba(0,0,0,0.4), 0 0 0 1px rgba(77,168,255,0.2);
    }}

    .card-prob-bar {{
      height: 3px;
      background: linear-gradient(to right, var(--green-dim), var(--green-safe), var(--blue-highlight));
      width: var(--prob-width, 80%);
      transition: width 0.6s ease;
    }}

    .card-header {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 18px 22px 14px;
    }}

    .card-set-id {{ display: flex; align-items: center; gap: 10px; }}

    .set-number {{
      font-family: 'Bebas Neue', sans-serif;
      font-size: 32px; letter-spacing: 1px;
      color: var(--silver-dim); line-height: 1;
    }}

    .set-label {{
      font-size: 10px; letter-spacing: 2.5px;
      text-transform: uppercase; color: var(--silver-muted);
    }}

    .card-prob-badge {{ display: flex; flex-direction: column; align-items: flex-end; }}

    .prob-pct {{
      font-family: 'Bebas Neue', sans-serif;
      font-size: 36px; letter-spacing: 1px;
      color: var(--silver-shine); line-height: 1;
    }}

    .prob-pct.high {{ color: var(--green-safe); text-shadow: 0 0 20px rgba(30,255,142,0.4); }}
    .prob-pct.mid  {{ color: var(--gold-accent); }}
    .prob-pct.low  {{ color: var(--silver-dim); }}

    .prob-label {{
      font-size: 9px; letter-spacing: 2px;
      text-transform: uppercase; color: var(--silver-muted);
    }}

    .bets-table {{ border-top: 1px solid rgba(100,160,255,0.08); padding: 0 22px; }}

    .bet-row {{
      display: grid; grid-template-columns: 1fr auto auto;
      align-items: center; gap: 16px;
      padding: 12px 0;
      border-bottom: 1px solid rgba(100,160,255,0.06);
      transition: background 0.15s;
    }}

    .bet-row:last-child {{ border-bottom: none; }}

    .bet-row:hover {{
      background: rgba(30,60,120,0.2);
      margin: 0 -22px;
      padding-left: 22px; padding-right: 22px;
      border-radius: 6px;
    }}

    .bet-match {{ font-size: 13px; font-weight: 500; color: var(--silver-bright); }}
    .bet-market {{ font-size: 11px; color: var(--silver-muted); margin-top: 2px; }}

    .bet-prob-bar-wrap {{
      width: 80px; height: 4px;
      background: rgba(100,150,255,0.12);
      border-radius: 2px; overflow: hidden;
    }}

    .bet-prob-bar-fill {{
      height: 100%; border-radius: 2px;
      background: linear-gradient(to right, var(--green-dim), var(--green-safe));
      transition: width 0.6s ease;
    }}

    .bet-prob-pct {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px; font-weight: 600;
      color: var(--green-safe);
      white-space: nowrap; text-align: right; min-width: 42px;
    }}

    .card-footer {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 14px 22px;
      background: rgba(5,15,38,0.5);
      border-top: 1px solid rgba(100,160,255,0.08);
    }}

    .odds-label {{
      font-size: 10px; letter-spacing: 2px;
      text-transform: uppercase; color: var(--silver-muted);
    }}

    .odds-value {{
      font-family: 'Bebas Neue', sans-serif;
      font-size: 28px; letter-spacing: 1px;
      color: var(--gold-accent);
      text-shadow: 0 0 12px rgba(201,168,76,0.3);
    }}

    .stake-badge {{ display: flex; flex-direction: column; align-items: flex-end; }}

    .stake-label {{
      font-size: 9px; letter-spacing: 2px;
      text-transform: uppercase; color: var(--silver-muted);
    }}

    .stake-val {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 16px; font-weight: 600; color: var(--silver-bright);
    }}

    .stake-return {{
      font-size: 11px; color: var(--green-safe);
      font-family: 'JetBrains Mono', monospace;
    }}

    .warning-card {{
      background: rgba(10,20,45,0.7);
      border: 1px dashed rgba(201,168,76,0.35);
      border-radius: 16px; padding: 40px 32px;
      text-align: center; animation: slide-in 0.4s ease both;
    }}

    .warning-icon {{ font-size: 40px; margin-bottom: 16px; opacity: 0.8; }}

    .warning-title {{
      font-family: 'Bebas Neue', sans-serif;
      font-size: 24px; letter-spacing: 2px;
      color: var(--gold-accent); margin-bottom: 10px;
    }}

    .warning-text {{
      font-size: 14px; color: var(--silver-muted);
      line-height: 1.7; max-width: 420px; margin: 0 auto;
    }}

    .loading-overlay {{
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      gap: 20px; padding: 60px;
    }}

    .spinner {{
      width: 44px; height: 44px;
      border: 3px solid rgba(77,168,255,0.15);
      border-top-color: var(--blue-highlight);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }}

    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

    .loading-text {{
      font-size: 12px; letter-spacing: 3px;
      text-transform: uppercase; color: var(--silver-muted);
    }}

    ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: rgba(100,150,255,0.2); border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: rgba(100,150,255,0.4); }}

    @media (max-width: 900px) {{
      .app-shell {{ grid-template-columns: 1fr; grid-template-rows: auto; }}
      .sidebar {{ border-right: none; border-bottom: 1px solid rgba(100,160,255,0.1); padding: 20px 16px; }}
      .main {{ padding: 20px 16px; }}
      .bet-row {{ grid-template-columns: 1fr auto; }}
      .bet-prob-bar-wrap {{ display: none; }}
    }}
  </style>
</head>
<body>
<div class="app-shell">

  <header class="header">
    <div class="header-brand">
      <div class="brand-icon">&#x26BD;</div>
      <div>
        <div class="brand-name">Probability Engine</div>
        <div class="brand-sub">Football Betting Analytics</div>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:24px;">
      <div class="header-status">
        <div class="status-dot"></div>
        Live Data
      </div>
      <div class="header-time" id="live-clock">--:--:--</div>
    </div>
  </header>

  <aside class="sidebar">
    <div>
      <div class="sidebar-section-label">Bankroll</div>
      <div class="bankroll-card">
        <div class="bankroll-label">Available Capital</div>
        <div class="bankroll-value">
          <span class="bankroll-currency">&#8364;</span>
          <span id="bankroll-display">{bankroll:,}</span>
        </div>
        <div class="bankroll-slider-wrapper">
          <input type="range" id="bankroll-slider"
            min="100" max="20000" step="50" value="{bankroll}"
            oninput="updateBankroll(this.value)">
          <div class="bankroll-range-labels">
            <span>&#8364;100</span><span>&#8364;20,000</span>
          </div>
        </div>
      </div>
    </div>

    <div>
      <div class="sidebar-section-label">Model</div>
      <div class="model-pills">
        <button class="model-pill {'active' if model == 'xG Only' else ''}"
          onclick="selectModel(this,'xG Only')">
          <span class="pill-dot"></span>xG Only
        </button>
        <button class="model-pill {'active' if model == 'Market-Blended' else ''}"
          onclick="selectModel(this,'Market-Blended')">
          <span class="pill-dot"></span>Market-Blended
        </button>
      </div>
    </div>

    <div>
      <div class="sidebar-section-label">Session Stats</div>
      <div class="sidebar-stats">
        <div class="stat-row">
          <span class="stat-name">Fixtures Loaded</span>
          <span class="stat-val" id="stat-fixtures">&#8212;</span>
        </div>
        <div class="stat-row">
          <span class="stat-name">Sets Generated</span>
          <span class="stat-val good" id="stat-sets">&#8212;</span>
        </div>
        <div class="stat-row">
          <span class="stat-name">Avg Probability</span>
          <span class="stat-val warn" id="stat-avgprob">&#8212;</span>
        </div>
        <div class="stat-row">
          <span class="stat-name">Active Model</span>
          <span class="stat-val" id="stat-model">{model}</span>
        </div>
      </div>
    </div>
  </aside>

  <main class="main">
    <div class="page-header">
      <div>
        <div class="page-title">TOP BET <span>SETS</span></div>
        <div class="page-subtitle" id="subtitle">
          &#8805;70% combined probability threshold &middot; Powered by xG modeling
        </div>
      </div>
      <button class="refresh-btn" onclick="window.location.reload()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2.5">
          <path d="M23 4v6h-6"/><path d="M1 20v-6h6"/>
          <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
        </svg>
        Refresh
      </button>
    </div>

    <div class="filter-bar">
      <span class="filter-label">Threshold</span>
      <div class="threshold-pills">
        <button class="thr-pill" onclick="setThreshold(this,60)">&#8805;60%</button>
        <button class="thr-pill active" onclick="setThreshold(this,70)">&#8805;70%</button>
        <button class="thr-pill" onclick="setThreshold(this,80)">&#8805;80%</button>
        <button class="thr-pill" onclick="setThreshold(this,90)">&#8805;90%</button>
      </div>
      <div class="filter-divider"></div>
      <div class="sets-count-badge">
        <span class="count-num" id="visible-count">0</span>
        <span>sets shown</span>
      </div>
    </div>

    <div class="section-heading">
      Safe Bet Sets
      <span class="heading-badge">&#9679; SAFE</span>
    </div>

    <div id="content-area">
      <div class="loading-overlay">
        <div class="spinner"></div>
        <div class="loading-text">Loading Sets&#8230;</div>
      </div>
    </div>
  </main>
</div>

<script>
  // ── Data injected by Python/Streamlit ──────────────────────────────────────
  const PYTHON_SETS   = {sets_json};
  const PYTHON_BANKROLL = {bankroll};
  const NO_DATA       = {'true' if no_data else 'false'};

  // ── State ──────────────────────────────────────────────────────────────────
  let bankroll  = PYTHON_BANKROLL;
  let threshold = 50;
  let allSets   = PYTHON_SETS;

  // ── Boot ───────────────────────────────────────────────────────────────────
  window.addEventListener('DOMContentLoaded', () => {{
    updateBankroll(bankroll);
    updateClock();
    setInterval(updateClock, 1000);

    if (NO_DATA) {{
      showNoData();
    }} else {{
      renderSets(allSets, threshold);
    }}

    const avg = allSets.length
      ? (allSets.reduce((a, s) => a + s.prob, 0) / allSets.length * 100).toFixed(1) + '%'
      : '&#8212;';
    document.getElementById('stat-fixtures').textContent = allSets.length > 0 ? allSets.length : '0';
    document.getElementById('stat-sets').textContent     = allSets.length;
    document.getElementById('stat-avgprob').textContent  = avg;
  }});

  // ── Render ─────────────────────────────────────────────────────────────────
  function renderSets(sets, thr) {{
    const area     = document.getElementById('content-area');
    const filtered = sets.filter(s => s.prob * 100 >= thr).slice(0, 5);
    document.getElementById('visible-count').textContent = filtered.length;

    if (filtered.length === 0) {{
      showNoData(thr);
      return;
    }}

    area.innerHTML = '<div class="sets-grid">'
      + filtered.map((s, i) => buildCard(s, i)).join('')
      + '</div>';
  }}

  function showNoData(thr) {{
    const t = thr || threshold;
    document.getElementById('content-area').innerHTML = `
      <div class="warning-card">
        <div class="warning-icon">&#9888;&#65039;</div>
        <div class="warning-title">No Sets Above ${{t}}%</div>
        <div class="warning-text">
          No bet sets meet the ${{t}}% probability threshold today.
          This typically occurs on low-fixture or high-variance days
          (e.g. Champions League matchdays). Try lowering the threshold.
        </div>
      </div>`;
  }}

  function probClass(p) {{
    if (p >= 0.82) return 'high';
    if (p >= 0.72) return 'mid';
    return 'low';
  }}

  function buildCard(s, i) {{
    const pct       = (s.prob * 100).toFixed(1);
    const stake     = (bankroll * 0.03).toFixed(2);
    const potReturn = (parseFloat(stake) * s.odds).toFixed(2);

    const betsHtml = s.bets.map(b => `
      <div class="bet-row">
        <div>
          <div class="bet-match">${{b.match}}</div>
          <div class="bet-market">${{b.market}}</div>
        </div>
        <div class="bet-prob-bar-wrap">
          <div class="bet-prob-bar-fill" style="width:${{(b.prob*100).toFixed(0)}}%"></div>
        </div>
        <div class="bet-prob-pct">${{(b.prob*100).toFixed(1)}}%</div>
      </div>`).join('');

    return `
      <div class="bet-set-card">
        <div class="card-prob-bar" style="--prob-width:${{pct}}%"></div>
        <div class="card-header">
          <div class="card-set-id">
            <div class="set-number">#${{String(i+1).padStart(2,'0')}}</div>
            <div>
              <div style="font-size:12px;font-weight:600;color:var(--silver-bright)">BET SET</div>
              <div class="set-label">${{s.bets.length}} selections</div>
            </div>
          </div>
          <div class="card-prob-badge">
            <div class="prob-pct ${{probClass(s.prob)}}">${{pct}}%</div>
            <div class="prob-label">Combined Prob.</div>
          </div>
        </div>
        <div class="bets-table">${{betsHtml}}</div>
        <div class="card-footer">
          <div class="odds-display">
            <div>
              <div class="odds-label">Total Odds</div>
              <div class="odds-value">${{s.odds.toFixed(2)}}</div>
            </div>
          </div>
          <div class="stake-badge">
            <div class="stake-label">Suggested Stake</div>
            <div class="stake-val">&#8364;${{stake}}</div>
            <div class="stake-return">&#8594; &#8364;${{potReturn}} return</div>
          </div>
        </div>
      </div>`;
  }}

  // ── Controls ───────────────────────────────────────────────────────────────
  function updateBankroll(val) {{
    bankroll = parseInt(val);
    document.getElementById('bankroll-display').textContent
      = bankroll.toLocaleString('en-GB');
    const pct = ((bankroll - 100) / (20000 - 100)) * 100;
    const slider = document.getElementById('bankroll-slider');
    slider.value = bankroll;
    slider.style.setProperty('--progress', pct + '%');
    if (allSets.length) renderSets(allSets, threshold);
  }}

  function selectModel(el, model) {{
    document.querySelectorAll('.model-pill').forEach(p => p.classList.remove('active'));
    el.classList.add('active');
    document.getElementById('stat-model').textContent = model;
    // Triggers a full Streamlit re-run via URL param
    const url = new URL(window.location.href);
    url.searchParams.set('model', model);
    window.location.href = url.toString();
  }}

  function setThreshold(el, val) {{
    document.querySelectorAll('.thr-pill').forEach(p => p.classList.remove('active'));
    el.classList.add('active');
    threshold = val;
    document.getElementById('subtitle').textContent =
      `\u2265${{threshold}}% combined probability threshold \u00B7 Powered by xG modeling`;
    renderSets(allSets, threshold);
  }}

  // ── Clock ──────────────────────────────────────────────────────────────────
  function updateClock() {{
    const now = new Date();
    const pad = n => String(n).padStart(2,'0');
    document.getElementById('live-clock').textContent =
      `${{pad(now.getHours())}}:${{pad(now.getMinutes())}}:${{pad(now.getSeconds())}}`;
  }}
</script>
</body>
</html>"""

# Render — height covers a full dashboard without scrollbars on most screens
st.components.v1.html(html, height=960, scrolling=True)
