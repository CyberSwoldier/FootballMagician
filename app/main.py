<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Football Betting Probability Engine</title>
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    :root {
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
      --glow-navy: rgba(30, 80, 180, 0.3);
      --glow-silver: rgba(200, 220, 255, 0.15);
    }

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'DM Sans', sans-serif;
      background: var(--navy-deepest);
      color: var(--silver-pale);
      min-height: 900px;
      overflow-x: hidden;
    }

    /* Background layers */
    body::before {
      content: '';
      position: fixed;
      inset: 0;
      background:
        radial-gradient(ellipse 80% 60% at 15% 10%, rgba(20, 60, 140, 0.4) 0%, transparent 60%),
        radial-gradient(ellipse 60% 50% at 85% 80%, rgba(10, 35, 90, 0.5) 0%, transparent 55%),
        radial-gradient(ellipse 40% 40% at 50% 50%, rgba(5, 15, 40, 0.9) 0%, transparent 100%);
      pointer-events: none;
      z-index: 0;
    }

    /* Subtle grid overlay */
    body::after {
      content: '';
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(rgba(100, 150, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(100, 150, 255, 0.03) 1px, transparent 1px);
      background-size: 40px 40px;
      pointer-events: none;
      z-index: 0;
    }

    /* ===== LAYOUT ===== */
    .app-shell {
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: 280px 1fr;
      grid-template-rows: 72px 1fr;
      min-height: 100vh;
    }

    /* ===== HEADER ===== */
    .header {
      grid-column: 1 / -1;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 32px;
      background: rgba(4, 13, 26, 0.95);
      border-bottom: 1px solid rgba(100, 160, 255, 0.12);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      position: sticky;
      top: 0;
      z-index: 100;
    }

    .header-brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }

    .brand-icon {
      width: 38px;
      height: 38px;
      background: linear-gradient(135deg, var(--navy-accent), var(--blue-highlight));
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      box-shadow: 0 0 20px rgba(77, 168, 255, 0.35);
      animation: icon-pulse 3s ease-in-out infinite;
    }

    @keyframes icon-pulse {
      0%, 100% { box-shadow: 0 0 20px rgba(77, 168, 255, 0.35); }
      50% { box-shadow: 0 0 35px rgba(77, 168, 255, 0.6); }
    }

    .brand-name {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 22px;
      letter-spacing: 2px;
      color: var(--silver-bright);
      line-height: 1;
    }

    .brand-sub {
      font-size: 10px;
      letter-spacing: 3px;
      color: var(--silver-dim);
      text-transform: uppercase;
      margin-top: 2px;
    }

    .header-status {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: var(--silver-dim);
      letter-spacing: 1px;
      text-transform: uppercase;
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--green-safe);
      box-shadow: 0 0 8px var(--green-safe);
      animation: blink 2s ease-in-out infinite;
    }

    @keyframes blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.3; }
    }

    .header-time {
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
      color: var(--silver-dim);
    }

    /* ===== SIDEBAR ===== */
    .sidebar {
      background: rgba(7, 20, 40, 0.9);
      border-right: 1px solid rgba(100, 160, 255, 0.1);
      padding: 28px 20px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 28px;
    }

    .sidebar-section-label {
      font-size: 10px;
      letter-spacing: 3px;
      text-transform: uppercase;
      color: var(--silver-muted);
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .sidebar-section-label::after {
      content: '';
      flex: 1;
      height: 1px;
      background: rgba(100, 160, 255, 0.12);
    }

    /* Bankroll display */
    .bankroll-card {
      background: linear-gradient(135deg, rgba(26, 58, 112, 0.6), rgba(10, 31, 64, 0.8));
      border: 1px solid rgba(100, 160, 255, 0.18);
      border-radius: 14px;
      padding: 20px 18px;
      position: relative;
      overflow: hidden;
    }

    .bankroll-card::before {
      content: '';
      position: absolute;
      top: -30px; right: -30px;
      width: 100px;
      height: 100px;
      background: radial-gradient(circle, rgba(77, 168, 255, 0.15), transparent 70%);
      pointer-events: none;
    }

    .bankroll-label {
      font-size: 10px;
      letter-spacing: 2.5px;
      text-transform: uppercase;
      color: var(--silver-muted);
      margin-bottom: 8px;
    }

    .bankroll-value {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 42px;
      letter-spacing: 1px;
      color: var(--silver-shine);
      line-height: 1;
    }

    .bankroll-currency {
      font-size: 20px;
      color: var(--gold-accent);
      vertical-align: super;
      font-family: 'DM Sans', sans-serif;
      font-weight: 300;
    }

    .bankroll-slider-wrapper {
      margin-top: 14px;
    }

    input[type="range"] {
      -webkit-appearance: none;
      width: 100%;
      height: 4px;
      border-radius: 2px;
      background: linear-gradient(to right, var(--blue-highlight) 0%, var(--blue-highlight) var(--progress, 25%), rgba(100,150,255,0.2) var(--progress, 25%));
      outline: none;
      cursor: pointer;
    }

    input[type="range"]::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: var(--silver-bright);
      box-shadow: 0 0 10px rgba(77, 168, 255, 0.6);
      cursor: pointer;
      transition: box-shadow 0.2s;
    }

    input[type="range"]::-webkit-slider-thumb:hover {
      box-shadow: 0 0 18px rgba(77, 168, 255, 0.9);
    }

    .bankroll-range-labels {
      display: flex;
      justify-content: space-between;
      font-size: 10px;
      color: var(--silver-muted);
      margin-top: 6px;
      font-family: 'JetBrains Mono', monospace;
    }

    /* Model selector */
    .model-pills {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .model-pill {
      padding: 12px 16px;
      border-radius: 10px;
      border: 1px solid rgba(100, 160, 255, 0.14);
      background: transparent;
      color: var(--silver-dim);
      font-family: 'DM Sans', sans-serif;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.25s ease;
      text-align: left;
      display: flex;
      align-items: center;
      gap: 10px;
      letter-spacing: 0.3px;
    }

    .model-pill:hover {
      background: rgba(30, 60, 120, 0.4);
      border-color: rgba(100, 160, 255, 0.3);
      color: var(--silver-bright);
    }

    .model-pill.active {
      background: linear-gradient(135deg, rgba(30, 80, 180, 0.5), rgba(20, 50, 120, 0.6));
      border-color: rgba(77, 168, 255, 0.5);
      color: var(--silver-shine);
      box-shadow: 0 0 20px rgba(30, 80, 180, 0.3), inset 0 1px 0 rgba(255,255,255,0.08);
    }

    .pill-dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      background: var(--silver-muted);
      transition: all 0.25s;
      flex-shrink: 0;
    }

    .model-pill.active .pill-dot {
      background: var(--blue-highlight);
      box-shadow: 0 0 8px var(--blue-highlight);
    }

    /* Stats strip in sidebar */
    .sidebar-stats {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .stat-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 14px;
      background: rgba(10, 20, 45, 0.6);
      border-radius: 8px;
      border: 1px solid rgba(100, 160, 255, 0.07);
    }

    .stat-name {
      font-size: 11px;
      color: var(--silver-muted);
      letter-spacing: 0.5px;
    }

    .stat-val {
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
      font-weight: 600;
      color: var(--silver-bright);
    }

    .stat-val.good { color: var(--green-safe); }
    .stat-val.warn { color: var(--gold-accent); }

    /* ===== MAIN CONTENT ===== */
    .main {
      padding: 32px 36px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 28px;
    }

    /* Page title section */
    .page-header {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
    }

    .page-title {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 48px;
      letter-spacing: 3px;
      color: var(--silver-shine);
      line-height: 1;
    }

    .page-title span {
      color: var(--blue-highlight);
    }

    .page-subtitle {
      font-size: 13px;
      color: var(--silver-muted);
      letter-spacing: 1px;
      margin-top: 4px;
    }

    .refresh-btn {
      padding: 10px 20px;
      border-radius: 8px;
      border: 1px solid rgba(77, 168, 255, 0.35);
      background: rgba(20, 50, 110, 0.3);
      color: var(--blue-highlight);
      font-family: 'DM Sans', sans-serif;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      gap: 8px;
      letter-spacing: 0.5px;
    }

    .refresh-btn:hover {
      background: rgba(20, 50, 110, 0.6);
      border-color: var(--blue-highlight);
      box-shadow: 0 0 16px rgba(77, 168, 255, 0.2);
    }

    /* Threshold filter bar */
    .filter-bar {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 14px 20px;
      background: rgba(10, 25, 55, 0.7);
      border: 1px solid rgba(100, 160, 255, 0.1);
      border-radius: 12px;
      backdrop-filter: blur(10px);
    }

    .filter-label {
      font-size: 11px;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: var(--silver-muted);
      white-space: nowrap;
    }

    .threshold-pills {
      display: flex;
      gap: 8px;
    }

    .thr-pill {
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 500;
      border: 1px solid rgba(100, 160, 255, 0.18);
      background: transparent;
      color: var(--silver-dim);
      cursor: pointer;
      transition: all 0.2s;
      font-family: 'JetBrains Mono', monospace;
    }

    .thr-pill:hover {
      border-color: rgba(100, 160, 255, 0.4);
      color: var(--silver-bright);
    }

    .thr-pill.active {
      background: rgba(30, 130, 80, 0.3);
      border-color: var(--green-safe);
      color: var(--green-safe);
    }

    .filter-divider {
      width: 1px;
      height: 24px;
      background: rgba(100, 160, 255, 0.12);
    }

    .sets-count-badge {
      margin-left: auto;
      display: flex;
      align-items: center;
      gap: 8px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
      color: var(--silver-dim);
    }

    .count-num {
      font-size: 18px;
      font-weight: 600;
      color: var(--green-safe);
    }

    /* Section heading */
    .section-heading {
      display: flex;
      align-items: center;
      gap: 12px;
      font-family: 'Bebas Neue', sans-serif;
      font-size: 22px;
      letter-spacing: 2px;
      color: var(--silver-bright);
    }

    .section-heading .heading-badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 4px 10px;
      border-radius: 20px;
      background: rgba(30, 130, 80, 0.2);
      border: 1px solid rgba(30, 255, 142, 0.3);
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 600;
      color: var(--green-safe);
      letter-spacing: 1px;
    }

    /* Bet sets grid */
    .sets-grid {
      display: flex;
      flex-direction: column;
      gap: 18px;
    }

    /* Individual bet set card */
    .bet-set-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      overflow: hidden;
      position: relative;
      transition: transform 0.25s ease, box-shadow 0.25s ease;
      animation: slide-in 0.4s ease both;
    }

    @keyframes slide-in {
      from { opacity: 0; transform: translateY(16px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .bet-set-card:nth-child(1) { animation-delay: 0.05s; }
    .bet-set-card:nth-child(2) { animation-delay: 0.1s; }
    .bet-set-card:nth-child(3) { animation-delay: 0.15s; }
    .bet-set-card:nth-child(4) { animation-delay: 0.2s; }
    .bet-set-card:nth-child(5) { animation-delay: 0.25s; }

    .bet-set-card:hover {
      transform: translateY(-2px);
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(77, 168, 255, 0.2);
    }

    /* Probability bar accent at top */
    .card-prob-bar {
      height: 3px;
      background: linear-gradient(to right, var(--green-dim), var(--green-safe), var(--blue-highlight));
      width: var(--prob-width, 80%);
      transition: width 0.6s ease;
    }

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 18px 22px 14px;
    }

    .card-set-id {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .set-number {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 32px;
      letter-spacing: 1px;
      color: var(--silver-dim);
      line-height: 1;
    }

    .set-label {
      font-size: 10px;
      letter-spacing: 2.5px;
      text-transform: uppercase;
      color: var(--silver-muted);
    }

    .card-prob-badge {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
    }

    .prob-pct {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 36px;
      letter-spacing: 1px;
      color: var(--silver-shine);
      line-height: 1;
    }

    .prob-pct.high { color: var(--green-safe); text-shadow: 0 0 20px rgba(30, 255, 142, 0.4); }
    .prob-pct.mid { color: var(--gold-accent); }
    .prob-pct.low { color: var(--silver-dim); }

    .prob-label {
      font-size: 9px;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: var(--silver-muted);
    }

    /* Bets table */
    .bets-table {
      border-top: 1px solid rgba(100, 160, 255, 0.08);
      padding: 0 22px;
    }

    .bet-row {
      display: grid;
      grid-template-columns: 1fr auto auto;
      align-items: center;
      gap: 16px;
      padding: 12px 0;
      border-bottom: 1px solid rgba(100, 160, 255, 0.06);
      transition: background 0.15s;
    }

    .bet-row:last-child { border-bottom: none; }

    .bet-row:hover {
      background: rgba(30, 60, 120, 0.2);
      margin: 0 -22px;
      padding-left: 22px;
      padding-right: 22px;
      border-radius: 6px;
    }

    .bet-match {
      font-size: 13px;
      font-weight: 500;
      color: var(--silver-bright);
      letter-spacing: 0.2px;
    }

    .bet-market {
      font-size: 11px;
      color: var(--silver-muted);
      margin-top: 2px;
      font-weight: 400;
    }

    .bet-prob-bar-wrap {
      width: 80px;
      height: 4px;
      background: rgba(100, 150, 255, 0.12);
      border-radius: 2px;
      overflow: hidden;
    }

    .bet-prob-bar-fill {
      height: 100%;
      border-radius: 2px;
      background: linear-gradient(to right, var(--green-dim), var(--green-safe));
      transition: width 0.6s ease;
    }

    .bet-prob-pct {
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      font-weight: 600;
      color: var(--green-safe);
      white-space: nowrap;
      text-align: right;
      min-width: 42px;
    }

    /* Card footer */
    .card-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 22px;
      background: rgba(5, 15, 38, 0.5);
      border-top: 1px solid rgba(100, 160, 255, 0.08);
    }

    .odds-display {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .odds-label {
      font-size: 10px;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: var(--silver-muted);
    }

    .odds-value {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 28px;
      letter-spacing: 1px;
      color: var(--gold-accent);
      text-shadow: 0 0 12px rgba(201, 168, 76, 0.3);
    }

    .stake-badge {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
    }

    .stake-label {
      font-size: 9px;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: var(--silver-muted);
    }

    .stake-val {
      font-family: 'JetBrains Mono', monospace;
      font-size: 16px;
      font-weight: 600;
      color: var(--silver-bright);
    }

    .stake-return {
      font-size: 11px;
      color: var(--green-safe);
      font-family: 'JetBrains Mono', monospace;
    }

    /* Warning state */
    .warning-card {
      background: rgba(10, 20, 45, 0.7);
      border: 1px dashed rgba(201, 168, 76, 0.35);
      border-radius: 16px;
      padding: 40px 32px;
      text-align: center;
      animation: slide-in 0.4s ease both;
    }

    .warning-icon {
      font-size: 40px;
      margin-bottom: 16px;
      opacity: 0.8;
    }

    .warning-title {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 24px;
      letter-spacing: 2px;
      color: var(--gold-accent);
      margin-bottom: 10px;
    }

    .warning-text {
      font-size: 14px;
      color: var(--silver-muted);
      line-height: 1.7;
      max-width: 420px;
      margin: 0 auto;
    }

    /* Loading state */
    .loading-overlay {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 20px;
      padding: 60px;
    }

    .spinner {
      width: 44px;
      height: 44px;
      border: 3px solid rgba(77, 168, 255, 0.15);
      border-top-color: var(--blue-highlight);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    .loading-text {
      font-size: 12px;
      letter-spacing: 3px;
      text-transform: uppercase;
      color: var(--silver-muted);
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(100, 150, 255, 0.2); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(100, 150, 255, 0.4); }

    /* Responsive */
    @media (max-width: 900px) {
      .app-shell {
        grid-template-columns: 1fr;
        grid-template-rows: auto;
      }
      .sidebar {
        border-right: none;
        border-bottom: 1px solid rgba(100, 160, 255, 0.1);
        padding: 20px 16px;
      }
      .main { padding: 20px 16px; }
      .bet-row { grid-template-columns: 1fr auto; }
      .bet-prob-bar-wrap { display: none; }
    }

    /* Number input hidden, driven by slider */
    .hidden { display: none; }
  </style>
</head>
<body>
<div class="app-shell">

  <!-- HEADER -->
  <header class="header">
    <div class="header-brand">
      <div class="brand-icon">⚽</div>
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
      <div class="header-time" id="live-clock">—</div>
    </div>
  </header>

  <!-- SIDEBAR -->
  <aside class="sidebar">

    <div>
      <div class="sidebar-section-label">Bankroll</div>
      <div class="bankroll-card">
        <div class="bankroll-label">Available Capital</div>
        <div class="bankroll-value">
          <span class="bankroll-currency">€</span>
          <span id="bankroll-display">1,000</span>
        </div>
        <div class="bankroll-slider-wrapper">
          <input type="range" id="bankroll-slider" min="100" max="20000" step="50" value="1000"
            oninput="updateBankroll(this.value)">
          <div class="bankroll-range-labels">
            <span>€100</span>
            <span>€20,000</span>
          </div>
        </div>
      </div>
    </div>

    <div>
      <div class="sidebar-section-label">Model</div>
      <div class="model-pills">
        <button class="model-pill active" onclick="selectModel(this, 'xG Only')">
          <span class="pill-dot"></span>
          xG Only
        </button>
        <button class="model-pill" onclick="selectModel(this, 'Market-Blended')">
          <span class="pill-dot"></span>
          Market-Blended
        </button>
      </div>
    </div>

    <div>
      <div class="sidebar-section-label">Session Stats</div>
      <div class="sidebar-stats">
        <div class="stat-row">
          <span class="stat-name">Fixtures Loaded</span>
          <span class="stat-val" id="stat-fixtures">—</span>
        </div>
        <div class="stat-row">
          <span class="stat-name">Sets Generated</span>
          <span class="stat-val good" id="stat-sets">—</span>
        </div>
        <div class="stat-row">
          <span class="stat-name">Avg Probability</span>
          <span class="stat-val warn" id="stat-avgprob">—</span>
        </div>
        <div class="stat-row">
          <span class="stat-name">Active Model</span>
          <span class="stat-val" id="stat-model">xG Only</span>
        </div>
      </div>
    </div>

  </aside>

  <!-- MAIN -->
  <main class="main">

    <div class="page-header">
      <div>
        <div class="page-title">TOP BET <span>SETS</span></div>
        <div class="page-subtitle">≥70% combined probability threshold · Powered by xG modeling</div>
      </div>
      <button class="refresh-btn" onclick="loadData()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M23 4v6h-6"/><path d="M1 20v-6h6"/>
          <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
        </svg>
        Refresh
      </button>
    </div>

    <!-- Filter bar -->
    <div class="filter-bar">
      <span class="filter-label">Threshold</span>
      <div class="threshold-pills">
        <button class="thr-pill" onclick="setThreshold(this, 60)">≥60%</button>
        <button class="thr-pill active" onclick="setThreshold(this, 70)">≥70%</button>
        <button class="thr-pill" onclick="setThreshold(this, 80)">≥80%</button>
        <button class="thr-pill" onclick="setThreshold(this, 90)">≥90%</button>
      </div>
      <div class="filter-divider"></div>
      <div class="sets-count-badge">
        <span class="count-num" id="visible-count">0</span>
        <span>sets shown</span>
      </div>
    </div>

    <div class="section-heading">
      Safe Bet Sets
      <span class="heading-badge">● SAFE</span>
    </div>

    <!-- Content area -->
    <div id="content-area">
      <div class="loading-overlay">
        <div class="spinner"></div>
        <div class="loading-text">Fetching Fixtures…</div>
      </div>
    </div>

  </main>
</div>

<script>
  // ─── State ───────────────────────────────────────────────────────────────────
  let bankroll = 1000;
  let activeModel = 'xG Only';
  let threshold = 70;
  let allSets = [];

  // ─── Demo data generator (mirrors real generate_sets output) ────────────────
  function makeDemoSets() {
    const teams = [
      ['Arsenal', 'Chelsea'], ['Barcelona', 'Real Madrid'], ['Man City', 'Liverpool'],
      ['PSG', 'Lyon'], ['Juventus', 'Napoli'], ['Ajax', 'PSV'],
      ['Dortmund', 'Bayern'], ['Inter', 'AC Milan'], ['Atletico', 'Sevilla'],
      ['Porto', 'Benfica']
    ];
    const markets = [
      'Over 1.5 Goals', 'Both Teams To Score', 'Home Win', 'Away Win',
      'Over 2.5 Goals', 'Draw No Bet (Home)', 'Asian HCP -0.5', 'Under 3.5 Goals'
    ];
    const numSets = 5 + Math.floor(Math.random() * 4);
    const sets = [];
    for (let i = 0; i < numSets; i++) {
      const numBets = 2 + Math.floor(Math.random() * 3);
      const bets = [];
      let combinedProb = 1;
      for (let j = 0; j < numBets; j++) {
        const pair = teams[Math.floor(Math.random() * teams.length)];
        const prob = 0.72 + Math.random() * 0.22;
        bets.push({
          match: `${pair[0]} vs ${pair[1]}`,
          market: markets[Math.floor(Math.random() * markets.length)],
          prob
        });
        combinedProb *= prob;
      }
      const adjustedProb = 0.70 + Math.random() * 0.25;
      const totalOdds = bets.reduce((acc, b) => acc * (1 / b.prob * 0.95), 1);
      sets.push({
        prob: adjustedProb,
        odds: parseFloat(Math.max(1.5, totalOdds).toFixed(2)),
        bets
      });
    }
    return sets.sort((a, b) => b.prob - a.prob);
  }

  // ─── Render ──────────────────────────────────────────────────────────────────
  function renderSets(sets, thr) {
    const area = document.getElementById('content-area');
    const filtered = sets.filter(s => s.prob * 100 >= thr).slice(0, 5);

    document.getElementById('visible-count').textContent = filtered.length;
    document.getElementById('stat-sets').textContent = sets.length;

    const avg = sets.length
      ? (sets.reduce((a, s) => a + s.prob, 0) / sets.length * 100).toFixed(1) + '%'
      : '—';
    document.getElementById('stat-avgprob').textContent = avg;

    if (filtered.length === 0) {
      area.innerHTML = `
        <div class="warning-card">
          <div class="warning-icon">⚠️</div>
          <div class="warning-title">No Sets Above ${thr}%</div>
          <div class="warning-text">
            No bet sets meeting the ${thr}% probability threshold today.
            This typically occurs on low-fixture or high-variance days
            (e.g. Champions League matchdays). Try lowering the threshold.
          </div>
        </div>`;
      return;
    }

    area.innerHTML = `<div class="sets-grid">${filtered.map((s, i) => buildCard(s, i)).join('')}</div>`;
  }

  function probClass(p) {
    if (p >= 0.82) return 'high';
    if (p >= 0.72) return 'mid';
    return 'low';
  }

  function buildCard(s, i) {
    const pct = (s.prob * 100).toFixed(1);
    const stake = (bankroll * 0.03).toFixed(2);
    const potReturn = (stake * s.odds).toFixed(2);
    const betsHtml = s.bets.map(b => `
      <div class="bet-row">
        <div>
          <div class="bet-match">${b.match}</div>
          <div class="bet-market">${b.market}</div>
        </div>
        <div class="bet-prob-bar-wrap">
          <div class="bet-prob-bar-fill" style="width:${(b.prob*100).toFixed(0)}%"></div>
        </div>
        <div class="bet-prob-pct">${(b.prob * 100).toFixed(1)}%</div>
      </div>`).join('');

    return `
      <div class="bet-set-card">
        <div class="card-prob-bar" style="--prob-width:${pct}%"></div>
        <div class="card-header">
          <div class="card-set-id">
            <div class="set-number">#${String(i + 1).padStart(2, '0')}</div>
            <div>
              <div style="font-size:12px;font-weight:600;color:var(--silver-bright);letter-spacing:.5px">BET SET</div>
              <div class="set-label">${s.bets.length} selections</div>
            </div>
          </div>
          <div class="card-prob-badge">
            <div class="prob-pct ${probClass(s.prob)}">${pct}%</div>
            <div class="prob-label">Combined Prob.</div>
          </div>
        </div>
        <div class="bets-table">${betsHtml}</div>
        <div class="card-footer">
          <div class="odds-display">
            <div>
              <div class="odds-label">Total Odds</div>
              <div class="odds-value">${s.odds.toFixed(2)}</div>
            </div>
          </div>
          <div class="stake-badge">
            <div class="stake-label">Suggested Stake</div>
            <div class="stake-val">€${stake}</div>
            <div class="stake-return">→ €${potReturn} return</div>
          </div>
        </div>
      </div>`;
  }

  // ─── Controls ────────────────────────────────────────────────────────────────
  function updateBankroll(val) {
    bankroll = parseInt(val);
    const fmt = bankroll.toLocaleString('en-GB');
    document.getElementById('bankroll-display').textContent = fmt;
    const pct = ((bankroll - 100) / (20000 - 100)) * 100;
    document.getElementById('bankroll-slider').style.setProperty('--progress', pct + '%');
    if (allSets.length) renderSets(allSets, threshold);
  }

  function selectModel(el, model) {
    document.querySelectorAll('.model-pill').forEach(p => p.classList.remove('active'));
    el.classList.add('active');
    activeModel = model;
    document.getElementById('stat-model').textContent = model;
    loadData();
  }

  function setThreshold(el, val) {
    document.querySelectorAll('.thr-pill').forEach(p => p.classList.remove('active'));
    el.classList.add('active');
    threshold = val;
    document.querySelector('.page-subtitle').textContent =
      `≥${threshold}% combined probability threshold · Powered by xG modeling`;
    renderSets(allSets, threshold);
  }

  // ─── Load data (simulated; replace API calls here) ───────────────────────────
  function loadData() {
    const area = document.getElementById('content-area');
    area.innerHTML = `<div class="loading-overlay"><div class="spinner"></div><div class="loading-text">Fetching Fixtures…</div></div>`;
    document.getElementById('stat-fixtures').textContent = '—';
    document.getElementById('stat-sets').textContent = '—';
    document.getElementById('stat-avgprob').textContent = '—';
    document.getElementById('visible-count').textContent = '0';

    // Simulate async fetch — swap with real fetch() calls to your Python backend
    setTimeout(() => {
      const fixtures = 8 + Math.floor(Math.random() * 10);
      document.getElementById('stat-fixtures').textContent = fixtures;
      allSets = makeDemoSets();
      renderSets(allSets, threshold);
    }, 900 + Math.random() * 600);
  }

  // ─── Live clock ──────────────────────────────────────────────────────────────
  function updateClock() {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    const s = String(now.getSeconds()).padStart(2, '0');
    document.getElementById('live-clock').textContent = `${h}:${m}:${s}`;
  }

  setInterval(updateClock, 1000);
  updateClock();

  // Initial slider styling
  updateBankroll(1000);
  loadData();
</script>
</body>
</html>
