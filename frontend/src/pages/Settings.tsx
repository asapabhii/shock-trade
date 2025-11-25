import { useState, useEffect } from 'react'
import { Save, RefreshCw, Power, PowerOff, AlertTriangle } from 'lucide-react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { api, TradingConfig } from '../lib/api'
import { useApi, usePolling } from '../hooks/useApi'
import { formatCurrency } from '../lib/utils'

export default function Settings() {
  const { data: config, refetch: refetchConfig } = useApi(() => api.getConfig())
  const { data: risk } = usePolling(() => api.getRiskStatus(), 5000)
  const { data: tradingStatus, refetch: refetchStatus } = usePolling(
    () =>
      api.getSystemStatus().then((s) => ({
        enabled: s.trading_enabled,
        kalshi: s.kalshi_connected,
      })),
    5000
  )

  const [formData, setFormData] = useState<Partial<TradingConfig>>({})
  const [saving, setSaving] = useState(false)
  const [tradingLoading, setTradingLoading] = useState(false)

  useEffect(() => {
    if (config) {
      setFormData(config)
    }
  }, [config])

  const handleChange = (field: keyof TradingConfig, value: number) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.updateConfig(formData)
      refetchConfig()
    } catch (e) {
      console.error('Failed to save config:', e)
    }
    setSaving(false)
  }

  const handleToggleTrading = async () => {
    setTradingLoading(true)
    try {
      if (tradingStatus?.enabled) {
        await api.disableTrading()
      } else {
        await api.enableTrading()
      }
      refetchStatus()
    } catch (e) {
      console.error('Failed to toggle trading:', e)
    }
    setTradingLoading(false)
  }

  const handleResetCircuitBreaker = async () => {
    try {
      await api.resetCircuitBreaker()
    } catch (e) {
      console.error('Failed to reset circuit breaker:', e)
    }
  }

  const handleKalshiLogin = async () => {
    try {
      await api.kalshiLogin()
      refetchStatus()
    } catch (e) {
      console.error('Failed to login to Kalshi:', e)
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-gray-400">Configure trading parameters and risk limits</p>
      </div>

      {/* Trading Controls */}
      <Card>
        <h2 className="text-lg font-medium text-white mb-4">Trading Controls</h2>
        <div className="flex flex-wrap gap-4">
          <Button
            variant={tradingStatus?.enabled ? 'danger' : 'success'}
            onClick={handleToggleTrading}
            loading={tradingLoading}
          >
            {tradingStatus?.enabled ? (
              <>
                <PowerOff className="w-4 h-4 mr-2" /> Disable Trading
              </>
            ) : (
              <>
                <Power className="w-4 h-4 mr-2" /> Enable Trading
              </>
            )}
          </Button>

          <Button variant="secondary" onClick={handleKalshiLogin}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Reconnect Kalshi
          </Button>

          {risk?.circuit_breaker_active && (
            <Button variant="danger" onClick={handleResetCircuitBreaker}>
              <AlertTriangle className="w-4 h-4 mr-2" />
              Reset Circuit Breaker
            </Button>
          )}
        </div>

        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-3 bg-dark-hover rounded-lg">
            <p className="text-xs text-gray-400">Trading</p>
            <p
              className={`font-medium ${
                tradingStatus?.enabled ? 'text-accent-green' : 'text-accent-red'
              }`}
            >
              {tradingStatus?.enabled ? 'Enabled' : 'Disabled'}
            </p>
          </div>
          <div className="p-3 bg-dark-hover rounded-lg">
            <p className="text-xs text-gray-400">Kalshi</p>
            <p
              className={`font-medium ${
                tradingStatus?.kalshi ? 'text-accent-green' : 'text-accent-red'
              }`}
            >
              {tradingStatus?.kalshi ? 'Connected' : 'Disconnected'}
            </p>
          </div>
          <div className="p-3 bg-dark-hover rounded-lg">
            <p className="text-xs text-gray-400">Circuit Breaker</p>
            <p
              className={`font-medium ${
                risk?.circuit_breaker_active
                  ? 'text-accent-red'
                  : 'text-accent-green'
              }`}
            >
              {risk?.circuit_breaker_active ? 'ACTIVE' : 'OK'}
            </p>
          </div>
          <div className="p-3 bg-dark-hover rounded-lg">
            <p className="text-xs text-gray-400">Errors</p>
            <p className="font-medium text-white">
              {risk?.consecutive_errors ?? 0}
            </p>
          </div>
        </div>
      </Card>

      {/* Trading Parameters */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-white">Trading Parameters</h2>
          <Button onClick={handleSave} loading={saving}>
            <Save className="w-4 h-4 mr-2" /> Save Changes
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Bankroll */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">
              Bankroll (Demo)
            </label>
            <input
              type="number"
              value={formData.bankroll ?? 0}
              onChange={(e) => handleChange('bankroll', parseFloat(e.target.value))}
              className="w-full bg-dark-hover border border-dark-border rounded-lg px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
            />
            <p className="text-xs text-gray-500 mt-1">
              Total demo capital for trading
            </p>
          </div>

          {/* Max Per Trade */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">
              Max Per Trade (%)
            </label>
            <input
              type="number"
              step="0.1"
              value={formData.max_per_trade_pct ?? 0}
              onChange={(e) =>
                handleChange('max_per_trade_pct', parseFloat(e.target.value))
              }
              className="w-full bg-dark-hover border border-dark-border rounded-lg px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
            />
            <p className="text-xs text-gray-500 mt-1">
              Maximum % of bankroll per trade
            </p>
          </div>

          {/* Underdog Threshold */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">
              Underdog Threshold
            </label>
            <input
              type="number"
              step="0.05"
              min="0"
              max="1"
              value={formData.underdog_threshold ?? 0}
              onChange={(e) =>
                handleChange('underdog_threshold', parseFloat(e.target.value))
              }
              className="w-full bg-dark-hover border border-dark-border rounded-lg px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
            />
            <p className="text-xs text-gray-500 mt-1">
              Team is underdog if probability below this (0-1)
            </p>
          </div>

          {/* Daily Loss Limit */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">
              Daily Loss Limit
            </label>
            <input
              type="number"
              value={formData.daily_loss_limit ?? 0}
              onChange={(e) =>
                handleChange('daily_loss_limit', parseFloat(e.target.value))
              }
              className="w-full bg-dark-hover border border-dark-border rounded-lg px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
            />
            <p className="text-xs text-gray-500 mt-1">
              Stop trading after this daily loss
            </p>
          </div>

          {/* Per Match Exposure */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">
              Per Match Max Exposure
            </label>
            <input
              type="number"
              value={formData.per_match_max_exposure ?? 0}
              onChange={(e) =>
                handleChange('per_match_max_exposure', parseFloat(e.target.value))
              }
              className="w-full bg-dark-hover border border-dark-border rounded-lg px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
            />
            <p className="text-xs text-gray-500 mt-1">
              Maximum exposure per single match
            </p>
          </div>

          {/* Take Profit */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">
              Take Profit (%)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={formData.take_profit_pct ?? 0}
              onChange={(e) =>
                handleChange('take_profit_pct', parseFloat(e.target.value))
              }
              className="w-full bg-dark-hover border border-dark-border rounded-lg px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
            />
            <p className="text-xs text-gray-500 mt-1">
              Auto-close at this profit % (0-1)
            </p>
          </div>
        </div>
      </Card>

      {/* Risk Status */}
      <Card>
        <h2 className="text-lg font-medium text-white mb-4">Current Risk Status</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-dark-hover rounded-lg">
            <p className="text-sm text-gray-400">Daily P/L</p>
            <p
              className={`text-xl font-bold ${
                (risk?.daily_pnl ?? 0) >= 0
                  ? 'text-accent-green'
                  : 'text-accent-red'
              }`}
            >
              {formatCurrency(risk?.daily_pnl ?? 0)}
            </p>
          </div>
          <div className="p-4 bg-dark-hover rounded-lg">
            <p className="text-sm text-gray-400">Daily Remaining</p>
            <p className="text-xl font-bold text-white">
              {formatCurrency(risk?.daily_loss_remaining ?? 0)}
            </p>
          </div>
          <div className="p-4 bg-dark-hover rounded-lg">
            <p className="text-sm text-gray-400">Current Exposure</p>
            <p className="text-xl font-bold text-white">
              {formatCurrency(risk?.current_exposure ?? 0)}
            </p>
          </div>
          <div className="p-4 bg-dark-hover rounded-lg">
            <p className="text-sm text-gray-400">Max Exposure</p>
            <p className="text-xl font-bold text-white">
              {formatCurrency(risk?.max_exposure ?? 0)}
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}
