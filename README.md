# ShockTrade

A multi-sport scoring-reaction trading bot with a modern dark-themed dashboard. This bot monitors live games across NFL, NBA, NHL, MLB, and Soccer, then executes trades on Kalshi prediction markets when underdog teams score.

This project is for educational and demonstration purposes only. It uses demo/sandbox APIs and no real money is involved.

---

## Supported Sports

| Sport | Data Source | API Key | Strategy |
|-------|-------------|---------|----------|
| NFL | ESPN | Not required | Underdog touchdown |
| NBA | ESPN | Not required | Underdog 10+ point run |
| NHL | ESPN | Not required | Underdog goal |
| MLB | ESPN | Not required | Underdog late-inning scoring |
| Soccer | Football-Data.org | Free key | Underdog goal |

All ESPN APIs are completely free with no rate limits. Football-Data.org offers a free tier with 10 requests per minute.

---

## Features

- Multi-sport monitoring via ESPN and Football-Data.org APIs
- Unified dashboard showing all sports in one view
- Sport-specific trading strategies optimized for each game type
- Underdog detection based on point spread or win probability
- Automated trading on Kalshi Demo when strategy conditions are met
- Risk management with per-trade limits, daily loss limits, and per-game exposure caps
- Position management with automatic take-profit and stop-loss
- Modern dark-themed React dashboard with real-time updates
- Click-to-expand game details with venue, spread, and position info
- SQLite database for trade history and metrics persistence

---

## Architecture

```
sports-trader/
├── sports/                  # Multi-sport architecture
│   ├── base.py              # Abstract base classes
│   ├── manager.py           # Unified sports manager
│   ├── nfl/                 # NFL provider + strategy
│   ├── nba/                 # NBA provider + strategy
│   ├── nhl/                 # NHL provider + strategy
│   ├── mlb/                 # MLB provider + strategy
│   └── soccer/              # Soccer provider + strategy
├── config/                  # Settings and configuration
├── core/                    # Risk manager, order executor, state
├── exchanges/               # Kalshi API client
├── services/                # Monitoring service
├── database/                # SQLite persistence
├── api/                     # FastAPI backend
│   └── routers/
│       ├── sports.py        # Unified sports API
│       ├── trades.py        # Trade history
│       ├── positions.py     # Open positions
│       └── system.py        # Bot control
├── frontend/                # React dashboard
└── tests/                   # Test suite
```

---

## Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher
- Kalshi Demo account

---

## API Keys Required

### Kalshi Demo (Required)

1. Go to https://demo.kalshi.com
2. Create an account
3. Navigate to Settings > API
4. Generate API credentials (key + RSA private key)

### Football-Data.org (For Soccer)

1. Go to https://www.football-data.org/client/register
2. Sign up for free
3. Copy your API key
4. Covers: Premier League, La Liga, Bundesliga, Serie A, Champions League

### ESPN (NFL, NBA, NHL, MLB)

No API key required. Works out of the box.

---

## Installation

### 1. Setup Python Environment

```powershell
cd goal-trader
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure Environment

```powershell
copy .env.example .env
notepad .env
```

Add your API keys to the .env file. Save your Kalshi RSA private key to `kalshi_private_key.pem`.

### 3. Setup Frontend

```powershell
cd frontend
npm install
cd ..
```

---

## Running the Application

### Terminal 1 - Backend

```powershell
cd goal-trader
.\venv\Scripts\Activate.ps1
python scripts/run_server.py
```

### Terminal 2 - Frontend

```powershell
cd goal-trader/frontend
npm run dev
```

Open http://localhost:5173 in your browser.

---

## API Endpoints

Full documentation at http://localhost:8000/docs

| Endpoint | Description |
|----------|-------------|
| GET /api/sports/summary | All sports status |
| GET /api/sports/games/today | All games today |
| GET /api/sports/games/live | Live games only |
| GET /api/sports/events/recent | Recent scoring events |
| POST /api/sports/refresh/{sport} | Refresh sport data |
| GET /api/trades/ | Trade history |
| GET /api/positions/ | Open positions |
| POST /api/positions/{id}/close | Close position |
| GET /api/metrics/ | Trading metrics |
| POST /api/system/bot/start | Start bot |
| POST /api/system/bot/stop | Stop bot |

---

## Trading Strategies

### NFL
- Trigger: Underdog scores touchdown (6+ points)
- Filter: First 3 quarters only, game within 21 points

### NBA
- Trigger: Underdog goes on 10+ point run
- Filter: First 3 quarters only, game within 25 points

### NHL
- Trigger: Underdog scores goal
- Filter: First 2 periods only, game within 3 goals

### MLB
- Trigger: Underdog scores in 6th inning or later
- Filter: Game within 5 runs

### Soccer
- Trigger: Underdog scores goal
- Filter: Game within 3 goals

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| BANKROLL | 10000 | Demo bankroll |
| MAX_PER_TRADE_PCT | 0.5 | Max % per trade |
| DAILY_LOSS_LIMIT | 500 | Stop after this loss |
| PER_MATCH_MAX_EXPOSURE | 200 | Max per game |
| TAKE_PROFIT_PCT | 0.15 | Exit at 15% gain |
| STOP_LOSS_PCT | 0.10 | Exit at 10% loss |

---

## Running Tests

```powershell
cd goal-trader
.\venv\Scripts\Activate.ps1
pytest tests/ -v
```

---

## Disclaimer

This project is for educational purposes only. It uses demo APIs and does not involve real money. I'm not responsible for any losses if modified for real trading.

---
