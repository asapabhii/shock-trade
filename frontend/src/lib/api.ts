/**
 * API client for Shock Trade backend
 */

const API_BASE = import.meta.env.VITE_API_URL || '/api'

// Simple request queue to prevent too many concurrent requests
let pendingRequests = 0
const MAX_CONCURRENT = 4

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  // Wait if too many requests pending
  while (pendingRequests >= MAX_CONCURRENT) {
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  
  pendingRequests++
  
  try {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 10000) // 10s timeout
    
    const response = await fetch(`${API_BASE}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      signal: controller.signal,
      ...options,
    })
    
    clearTimeout(timeoutId)

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`)
    }

    return response.json()
  } finally {
    pendingRequests--
  }
}

// Types
export interface Match {
  id: number
  league_name: string
  home_team: string
  away_team: string
  home_score: number
  away_score: number
  status: string
  minute: number | null
  kickoff: string
  has_open_position: boolean
}

export interface GoalEvent {
  id: string
  match_id: number
  timestamp: string
  minute: number
  scoring_team: string
  is_home_team: boolean
  score: string
}

export interface Trade {
  id: string
  match_id: number
  match_name: string
  market_id: string
  exchange: string
  outcome: string
  entry_price: number
  exit_price: number | null
  size: number
  pnl: number
  pnl_pct: number
  entry_time: string
  exit_time: string | null
  status: string
  reason: string
}

export interface Position {
  id: string
  match_id: number
  market_id: string
  exchange: string
  outcome: string
  size: number
  entry_price: number
  current_price: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  status: string
  opened_at: string
  time_open_mins: number
}

export interface Metrics {
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  total_pnl: number
  daily_pnl: number
  avg_pnl_per_trade: number
  avg_latency_ms: number
  max_latency_ms: number
  avg_slippage: number
  open_positions: number
  total_exposure: number
}

export interface RiskStatus {
  daily_pnl: number
  daily_loss_limit: number
  daily_loss_remaining: number
  current_exposure: number
  max_exposure: number
  consecutive_errors: number
  circuit_breaker_active: boolean
  last_error: string | null
}

export interface SystemStatus {
  goal_listener_running: boolean
  nfl_listener_running: boolean
  trading_enabled: boolean
  kalshi_connected: boolean
  live_matches_count: number
  live_nfl_games_count: number
  open_positions_count: number
  uptime_seconds: number
  mode: string
}

// NFL Types
export interface NFLTeam {
  id: number
  name: string
  abbreviation: string
  logo: string | null
}

export interface NFLGame {
  id: number
  home_team: NFLTeam
  away_team: NFLTeam
  home_score: number
  away_score: number
  status: string
  quarter: number
  clock: string
  kickoff: string
  venue: string | null
  spread: number | null
  over_under: number | null
  week: number | null
  has_open_position: boolean
}

export interface NFLScoringEvent {
  id: string
  game_id: number
  timestamp: string
  quarter: number
  clock: string
  scoring_team: string
  is_home_team: boolean
  points_scored: number
  scoring_type: string
  score: string
}

export interface TradingConfig {
  bankroll: number
  max_per_trade_pct: number
  underdog_threshold: number
  daily_loss_limit: number
  per_match_max_exposure: number
  take_profit_pct: number
  stop_loss_pct: number
}

// API functions
export const api = {
  // NFL Games
  getLiveNFLGames: () => fetchApi<NFLGame[]>('/nfl/games/live'),
  getAllNFLGames: () => fetchApi<NFLGame[]>('/nfl/games/all'),
  getRecentNFLScores: (limit = 20) => fetchApi<NFLScoringEvent[]>(`/nfl/scores?limit=${limit}`),
  refreshNFLGames: () => fetchApi<{ status: string; games_count: number; live_count: number }>('/nfl/refresh', { method: 'POST' }),

  // Soccer Matches (legacy)
  getLiveMatches: () => fetchApi<Match[]>('/matches/live'),
  getAllMatches: () => fetchApi<Match[]>('/matches/all'),
  getRecentGoals: (limit = 20) => fetchApi<GoalEvent[]>(`/matches/goals?limit=${limit}`),
  refreshMatches: () => fetchApi<{ status: string; matches_count: number }>('/matches/refresh', { method: 'POST' }),

  // Trades
  getTrades: (limit = 50) => fetchApi<Trade[]>(`/trades/?limit=${limit}`),
  getTradesForMatch: (matchId: number) => fetchApi<Trade[]>(`/trades/match/${matchId}`),

  // Positions
  getPositions: () => fetchApi<Position[]>('/positions/'),
  closePosition: (positionId: string, reason = 'manual') =>
    fetchApi<{ status: string; position_id: string; realized_pnl: number }>(
      `/positions/${positionId}/close?reason=${reason}`,
      { method: 'POST' }
    ),

  // Metrics
  getMetrics: () => fetchApi<Metrics>('/metrics/'),
  getRiskStatus: () => fetchApi<RiskStatus>('/metrics/risk'),
  getEquityCurve: () => fetchApi<{ timestamp: string; equity: number; pnl: number }[]>('/metrics/equity'),

  // Config
  getConfig: () => fetchApi<TradingConfig>('/config/'),
  updateConfig: (config: Partial<TradingConfig>) =>
    fetchApi<{ status: string; updated: Partial<TradingConfig> }>('/config/', {
      method: 'PATCH',
      body: JSON.stringify(config),
    }),
  enableTrading: () => fetchApi<{ status: string; trading_enabled: boolean }>('/config/trading/enable', { method: 'POST' }),
  disableTrading: () => fetchApi<{ status: string; trading_enabled: boolean }>('/config/trading/disable', { method: 'POST' }),
  resetCircuitBreaker: () => fetchApi<{ status: string }>('/config/reset-circuit-breaker', { method: 'POST' }),

  // System
  getSystemStatus: () => fetchApi<SystemStatus>('/system/status'),
  startBot: (mode = 'nfl') => fetchApi<{ status: string; mode: string }>(`/system/bot/start?mode=${mode}`, { method: 'POST' }),
  stopBot: () => fetchApi<{ status: string }>('/system/bot/stop', { method: 'POST' }),
  kalshiLogin: () => fetchApi<{ status: string; message: string }>('/system/kalshi/login', { method: 'POST' }),
}
