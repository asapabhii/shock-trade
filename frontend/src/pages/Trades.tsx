import { TrendingUp, TrendingDown } from 'lucide-react'
import { Table } from '../components/Table'
import { api, Trade } from '../lib/api'
import { formatCurrency, formatDateTime } from '../lib/utils'
import { usePolling } from '../hooks/useApi'
import { cn } from '../lib/utils'

export default function Trades() {
  const { data: trades, loading } = usePolling(() => api.getTrades(100), 10000)

  const columns = [
    {
      key: 'time',
      header: 'Time',
      render: (t: Trade) => (
        <span className="text-gray-400 text-sm">
          {formatDateTime(t.entry_time)}
        </span>
      ),
    },
    {
      key: 'match',
      header: 'Match',
      render: (t: Trade) => (
        <div>
          <p className="font-medium text-white">{t.match_name}</p>
          <p className="text-xs text-gray-500">{t.market_id}</p>
        </div>
      ),
    },
    {
      key: 'side',
      header: 'Side',
      render: (t: Trade) => (
        <span
          className={cn(
            'px-2 py-1 rounded text-xs font-medium',
            t.outcome === 'yes'
              ? 'bg-accent-green/20 text-accent-green'
              : 'bg-accent-red/20 text-accent-red'
          )}
        >
          {t.outcome.toUpperCase()}
        </span>
      ),
    },
    {
      key: 'entry',
      header: 'Entry',
      render: (t: Trade) => (
        <span className="font-mono">{(t.entry_price * 100).toFixed(0)}¢</span>
      ),
    },
    {
      key: 'exit',
      header: 'Exit',
      render: (t: Trade) =>
        t.exit_price ? (
          <span className="font-mono">{(t.exit_price * 100).toFixed(0)}¢</span>
        ) : (
          <span className="text-gray-500">-</span>
        ),
    },
    {
      key: 'size',
      header: 'Size',
      render: (t: Trade) => (
        <span className="font-mono">{formatCurrency(t.size)}</span>
      ),
    },
    {
      key: 'pnl',
      header: 'P/L',
      render: (t: Trade) => (
        <div className="flex items-center gap-1">
          {t.pnl > 0 ? (
            <TrendingUp className="w-4 h-4 text-accent-green" />
          ) : t.pnl < 0 ? (
            <TrendingDown className="w-4 h-4 text-accent-red" />
          ) : null}
          <span
            className={cn(
              'font-mono font-medium',
              t.pnl > 0 && 'text-accent-green',
              t.pnl < 0 && 'text-accent-red',
              t.pnl === 0 && 'text-gray-400'
            )}
          >
            {formatCurrency(t.pnl)}
          </span>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (t: Trade) => (
        <span
          className={cn(
            'px-2 py-1 rounded text-xs',
            t.status === 'open'
              ? 'bg-accent-blue/20 text-accent-blue'
              : 'bg-dark-hover text-gray-400'
          )}
        >
          {t.status}
        </span>
      ),
    },
  ]

  // Calculate summary stats
  const totalPnl = trades?.reduce((sum, t) => sum + t.pnl, 0) ?? 0
  const winningTrades = trades?.filter((t) => t.pnl > 0).length ?? 0
  const losingTrades = trades?.filter((t) => t.pnl < 0).length ?? 0

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Trade History</h1>
        <p className="text-gray-400">
          {trades?.length ?? 0} trades recorded
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-dark-card border border-dark-border rounded-xl p-4">
          <p className="text-sm text-gray-400">Total Trades</p>
          <p className="text-2xl font-bold text-white">{trades?.length ?? 0}</p>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-xl p-4">
          <p className="text-sm text-gray-400">Winning</p>
          <p className="text-2xl font-bold text-accent-green">{winningTrades}</p>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-xl p-4">
          <p className="text-sm text-gray-400">Losing</p>
          <p className="text-2xl font-bold text-accent-red">{losingTrades}</p>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-xl p-4">
          <p className="text-sm text-gray-400">Total P/L</p>
          <p
            className={cn(
              'text-2xl font-bold',
              totalPnl > 0 && 'text-accent-green',
              totalPnl < 0 && 'text-accent-red',
              totalPnl === 0 && 'text-white'
            )}
          >
            {formatCurrency(totalPnl)}
          </p>
        </div>
      </div>

      {/* Trades Table */}
      <Table
        columns={columns}
        data={trades ?? []}
        keyExtractor={(t) => t.id}
        loading={loading}
        emptyMessage="No trades yet. Trades will appear here when the bot executes orders."
      />
    </div>
  )
}
