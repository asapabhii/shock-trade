import { useState } from 'react'
import { X, Clock } from 'lucide-react'
import { Table } from '../components/Table'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { api, Position } from '../lib/api'
import { formatCurrency, formatPercent } from '../lib/utils'
import { usePolling } from '../hooks/useApi'
import { cn } from '../lib/utils'

export default function Positions() {
  const { data: positions, loading, refetch } = usePolling(
    () => api.getPositions(),
    5000
  )
  const [closingId, setClosingId] = useState<string | null>(null)

  const handleClose = async (positionId: string) => {
    setClosingId(positionId)
    try {
      await api.closePosition(positionId, 'manual')
      refetch()
    } catch (e) {
      console.error('Failed to close position:', e)
    }
    setClosingId(null)
  }

  const columns = [
    {
      key: 'market',
      header: 'Market',
      render: (p: Position) => (
        <div>
          <p className="font-medium text-white">{p.market_id}</p>
          <p className="text-xs text-gray-500">{p.exchange}</p>
        </div>
      ),
    },
    {
      key: 'outcome',
      header: 'Side',
      render: (p: Position) => (
        <span
          className={cn(
            'px-2 py-1 rounded text-xs font-medium',
            p.outcome === 'yes'
              ? 'bg-accent-green/20 text-accent-green'
              : 'bg-accent-red/20 text-accent-red'
          )}
        >
          {p.outcome.toUpperCase()}
        </span>
      ),
    },
    {
      key: 'size',
      header: 'Size',
      render: (p: Position) => (
        <span className="font-mono">{formatCurrency(p.size)}</span>
      ),
    },
    {
      key: 'entry',
      header: 'Entry',
      render: (p: Position) => (
        <span className="font-mono">{(p.entry_price * 100).toFixed(0)}¢</span>
      ),
    },
    {
      key: 'current',
      header: 'Current',
      render: (p: Position) => (
        <span className="font-mono">{(p.current_price * 100).toFixed(0)}¢</span>
      ),
    },
    {
      key: 'pnl',
      header: 'Unrealized P/L',
      render: (p: Position) => (
        <div>
          <span
            className={cn(
              'font-mono font-medium',
              p.unrealized_pnl > 0 && 'text-accent-green',
              p.unrealized_pnl < 0 && 'text-accent-red',
              p.unrealized_pnl === 0 && 'text-gray-400'
            )}
          >
            {formatCurrency(p.unrealized_pnl)}
          </span>
          <span className="text-xs text-gray-500 ml-2">
            ({formatPercent(p.unrealized_pnl_pct)})
          </span>
        </div>
      ),
    },
    {
      key: 'time',
      header: 'Time Open',
      render: (p: Position) => (
        <div className="flex items-center gap-1 text-gray-400">
          <Clock className="w-4 h-4" />
          <span>{p.time_open_mins.toFixed(0)}m</span>
        </div>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (p: Position) => (
        <Button
          variant="danger"
          size="sm"
          onClick={() => handleClose(p.id)}
          loading={closingId === p.id}
        >
          <X className="w-4 h-4" />
        </Button>
      ),
    },
  ]

  // Calculate totals
  const totalExposure = positions?.reduce((sum, p) => sum + p.size, 0) ?? 0
  const totalUnrealized =
    positions?.reduce((sum, p) => sum + p.unrealized_pnl, 0) ?? 0

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Open Positions</h1>
        <p className="text-gray-400">
          {positions?.length ?? 0} positions open
        </p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <p className="text-sm text-gray-400">Open Positions</p>
          <p className="text-2xl font-bold text-white">
            {positions?.length ?? 0}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-gray-400">Total Exposure</p>
          <p className="text-2xl font-bold text-white">
            {formatCurrency(totalExposure)}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-gray-400">Unrealized P/L</p>
          <p
            className={cn(
              'text-2xl font-bold',
              totalUnrealized > 0 && 'text-accent-green',
              totalUnrealized < 0 && 'text-accent-red',
              totalUnrealized === 0 && 'text-white'
            )}
          >
            {formatCurrency(totalUnrealized)}
          </p>
        </Card>
      </div>

      {/* Positions Table */}
      <Table
        columns={columns}
        data={positions ?? []}
        keyExtractor={(p) => p.id}
        loading={loading}
        emptyMessage="No open positions. Positions will appear here when the bot executes trades."
      />

      {/* Info */}
      {positions && positions.length > 0 && (
        <Card>
          <p className="text-sm text-gray-400">
            Positions are automatically managed with take-profit (15%) and
            stop-loss (10%) rules. You can also manually close positions using
            the X button.
          </p>
        </Card>
      )}
    </div>
  )
}
