import { useState } from 'react'
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  AlertTriangle,
  Play,
  Square,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { Card, StatCard } from '../components/Card'
import { Button } from '../components/Button'
import { api } from '../lib/api'
import { formatCurrency, formatPercent, formatTime, formatDuration } from '../lib/utils'
import { usePolling } from '../hooks/useApi'

interface SportsSummary {
  sports: Record<string, { live: number; today: number; status: string }>
  total_live: number
  total_today: number
}

interface ScoringEvent {
  id: string
  sport: string
  scoring_team: string
  points_scored: number
  scoring_type: string
  score: string
  timestamp: string
}

async function fetchSportsSummary(): Promise<SportsSummary> {
  const res = await fetch('/api/sports/summary')
  return res.json()
}

async function fetchRecentEvents(): Promise<ScoringEvent[]> {
  const res = await fetch('/api/sports/events/recent?limit=5')
  return res.json()
}

const SPORT_ICONS: Record<string, string> = {
  nfl: '🏈', nba: '🏀', nhl: '🏒', mlb: '⚾', soccer: '⚽'
}

export default function Dashboard() {
  const { data: metrics } = usePolling(() => api.getMetrics(), 10000)
  const { data: risk } = usePolling(() => api.getRiskStatus(), 10000)
  const { data: system, refetch: refetchSystem } = usePolling(() => api.getSystemStatus(), 5000)
  const { data: sportsSummary } = usePolling(fetchSportsSummary, 30000)
  const { data: recentEvents } = usePolling(fetchRecentEvents, 15000)
  const { data: equity } = usePolling(() => api.getEquityCurve(), 60000)

  const [botLoading, setBotLoading] = useState(false)

  const isBotRunning = system?.nfl_listener_running || system?.goal_listener_running

  const handleToggleBot = async () => {
    setBotLoading(true)
    try {
      if (isBotRunning) {
        await api.stopBot()
      } else {
        await api.startBot('nfl')
      }
      // Immediately refetch system status after action
      setTimeout(() => refetchSystem(), 500)
    } catch (e) {
      console.error('Failed to toggle bot:', e)
    }
    setBotLoading(false)
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-400">
            Multi-sport trading overview
            <span className="ml-2 text-accent-blue">
              ({sportsSummary?.total_live || 0} live / {sportsSummary?.total_today || 0} today)
            </span>
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Bot Status */}
          <div className="flex items-center gap-2">
            <div
              className={`w-3 h-3 rounded-full ${
                isBotRunning
                  ? 'bg-accent-green animate-pulse'
                  : 'bg-gray-500'
              }`}
            />
            <span className="text-sm text-gray-400">
              {isBotRunning ? 'Bot Running' : 'Bot Stopped'}
            </span>
          </div>
          <Button
            variant={isBotRunning ? 'danger' : 'success'}
            onClick={handleToggleBot}
            loading={botLoading}
          >
            {isBotRunning ? (
              <>
                <Square className="w-4 h-4 mr-2" /> Stop Bot
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" /> Start Bot
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Circuit Breaker Warning */}
      {risk?.circuit_breaker_active && (
        <div className="bg-accent-red/10 border border-accent-red rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-6 h-6 text-accent-red" />
          <div>
            <p className="font-medium text-accent-red">Circuit Breaker Active</p>
            <p className="text-sm text-gray-400">
              Trading halted due to consecutive errors. Last error: {risk.last_error}
            </p>
          </div>
          <Button
            variant="danger"
            size="sm"
            className="ml-auto"
            onClick={() => api.resetCircuitBreaker()}
          >
            Reset
          </Button>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total P/L"
          value={formatCurrency(metrics?.total_pnl ?? 0)}
          trend={metrics?.total_pnl && metrics.total_pnl > 0 ? 'up' : metrics?.total_pnl && metrics.total_pnl < 0 ? 'down' : 'neutral'}
          icon={metrics?.total_pnl && metrics.total_pnl >= 0 ? <TrendingUp /> : <TrendingDown />}
        />
        <StatCard
          title="Today's P/L"
          value={formatCurrency(metrics?.daily_pnl ?? 0)}
          trend={metrics?.daily_pnl && metrics.daily_pnl > 0 ? 'up' : metrics?.daily_pnl && metrics.daily_pnl < 0 ? 'down' : 'neutral'}
          subtitle={`Limit: ${formatCurrency(risk?.daily_loss_remaining ?? 0)} remaining`}
          icon={<Activity />}
        />
        <StatCard
          title="Win Rate"
          value={formatPercent((metrics?.win_rate ?? 0) * 100)}
          subtitle={`${metrics?.winning_trades ?? 0}W / ${metrics?.losing_trades ?? 0}L`}
          icon={<TrendingUp />}
        />
        <StatCard
          title="Avg Latency"
          value={`${(metrics?.avg_latency_ms ?? 0).toFixed(0)}ms`}
          subtitle={`Max: ${(metrics?.max_latency_ms ?? 0).toFixed(0)}ms`}
          icon={<Zap />}
        />
      </div>

      {/* Charts and Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity Curve */}
        <Card className="lg:col-span-2">
          <h3 className="text-lg font-medium text-white mb-4">Equity Curve</h3>
          {equity && equity.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={equity}>
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={(v) => formatTime(v)}
                  stroke="#6b7280"
                  fontSize={12}
                />
                <YAxis
                  tickFormatter={(v) => `$${v}`}
                  stroke="#6b7280"
                  fontSize={12}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#161b22',
                    border: '1px solid #30363d',
                    borderRadius: '8px',
                  }}
                  labelFormatter={(v) => formatTime(v as string)}
                  formatter={(v: number) => [formatCurrency(v), 'Equity']}
                />
                <Line
                  type="monotone"
                  dataKey="equity"
                  stroke="#3fb950"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-gray-400">
              No equity data yet. Complete some trades to see the chart.
            </div>
          )}
        </Card>

        {/* Recent Scoring Events */}
        <Card>
          <h3 className="text-lg font-medium text-white mb-4">Recent Scores</h3>
          {recentEvents && recentEvents.length > 0 ? (
            <div className="space-y-3">
              {recentEvents.map((event) => (
                <div
                  key={event.id}
                  className="flex items-center gap-3 p-3 bg-dark-hover rounded-lg"
                >
                  <div className="w-8 h-8 bg-accent-green/20 rounded-full flex items-center justify-center text-lg">
                    {SPORT_ICONS[event.sport] || '🎯'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">
                      {event.scoring_team}
                    </p>
                    <p className="text-xs text-gray-400">
                      +{event.points_scored} • {event.score}
                    </p>
                  </div>
                  <span className="text-xs text-gray-500">
                    {formatTime(event.timestamp)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-gray-400 py-8">
              No recent scores detected
            </div>
          )}
        </Card>
      </div>

      {/* Sports Status */}
      <Card>
        <h3 className="text-lg font-medium text-white mb-4">Sports Status</h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {sportsSummary?.sports && Object.entries(sportsSummary.sports).map(([sport, data]) => (
            <div key={sport} className="p-4 bg-dark-hover rounded-lg">
              <div className="flex items-center gap-2 mb-1">
                <span>{SPORT_ICONS[sport] || '🎯'}</span>
                <p className="text-sm text-gray-400 uppercase">{sport}</p>
              </div>
              <p className="text-xl font-bold text-white">
                {data.live} <span className="text-sm text-gray-500">/ {data.today}</span>
              </p>
            </div>
          ))}
        </div>
      </Card>

      {/* System Status */}
      <Card>
        <h3 className="text-lg font-medium text-white mb-4">System Status</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-dark-hover rounded-lg">
            <p className="text-sm text-gray-400">Total Live</p>
            <p className="text-xl font-bold text-white">
              {sportsSummary?.total_live ?? 0}
            </p>
          </div>
          <div className="p-4 bg-dark-hover rounded-lg">
            <p className="text-sm text-gray-400">Open Positions</p>
            <p className="text-xl font-bold text-white">
              {system?.open_positions_count ?? 0}
            </p>
          </div>
          <div className="p-4 bg-dark-hover rounded-lg">
            <p className="text-sm text-gray-400">Kalshi</p>
            <p className="text-xl font-bold">
              <span className={system?.kalshi_connected ? 'text-accent-green' : 'text-accent-red'}>
                {system?.kalshi_connected ? 'Connected' : 'Disconnected'}
              </span>
            </p>
          </div>
          <div className="p-4 bg-dark-hover rounded-lg">
            <p className="text-sm text-gray-400">Uptime</p>
            <p className="text-xl font-bold text-white">
              {formatDuration(system?.uptime_seconds ?? 0)}
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}
