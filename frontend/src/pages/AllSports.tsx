import { useState } from 'react'
import { RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { formatTime } from '../lib/utils'
import { usePolling } from '../hooks/useApi'

interface Team {
  id: number
  name: string
  abbreviation: string
  logo: string | null
}

interface Game {
  id: number
  sport: string
  home_team: Team
  away_team: Team
  home_score: number
  away_score: number
  status: string
  period: number
  clock: string
  start_time: string
  venue: string | null
  spread: number | null
  has_open_position: boolean
}

interface ScoringEvent {
  id: string
  game_id: number
  sport: string
  timestamp: string
  period: number
  clock: string
  scoring_team: string
  is_home_team: boolean
  points_scored: number
  scoring_type: string
  score: string
}

interface SportSummary {
  sports: Record<string, { live: number; today: number; status: string }>
  total_live: number
  total_today: number
}

const SPORT_CONFIG: Record<string, { name: string; color: string; icon: string }> = {
  nfl: { name: 'NFL', color: 'bg-green-600', icon: '🏈' },
  nba: { name: 'NBA', color: 'bg-orange-500', icon: '🏀' },
  nhl: { name: 'NHL', color: 'bg-blue-500', icon: '🏒' },
  mlb: { name: 'MLB', color: 'bg-red-500', icon: '⚾' },
  soccer: { name: 'Soccer', color: 'bg-emerald-500', icon: '⚽' }
}

async function fetchSummary(): Promise<SportSummary> {
  const res = await fetch('/api/sports/summary')
  if (!res.ok) throw new Error('Failed to fetch summary')
  return res.json()
}

async function fetchGames(): Promise<Game[]> {
  const res = await fetch('/api/sports/games/today')
  if (!res.ok) throw new Error('Failed to fetch games')
  return res.json()
}

async function fetchEvents(): Promise<ScoringEvent[]> {
  const res = await fetch('/api/sports/events/recent?limit=15')
  if (!res.ok) throw new Error('Failed to fetch events')
  return res.json()
}

export default function AllSports() {
  const { data: summary } = usePolling(fetchSummary, 30000)
  const { data: games, refetch: refetchGames, loading } = usePolling(fetchGames, 30000)
  const { data: events } = usePolling(fetchEvents, 15000)
  const [expandedSport, setExpandedSport] = useState<string | null>(null)
  const [selectedGame, setSelectedGame] = useState<Game | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await fetch('/api/sports/refresh/all', { method: 'POST' })
      refetchGames()
    } catch (e) {
      console.error('Refresh failed:', e)
    }
    setRefreshing(false)
  }

  const gamesBySport = games?.reduce((acc, game) => {
    if (!acc[game.sport]) acc[game.sport] = []
    acc[game.sport].push(game)
    return acc
  }, {} as Record<string, Game[]>) || {}

  const getStatusDisplay = (game: Game) => {
    if (game.status === 'final') return 'Final'
    if (game.status === 'scheduled') return formatTime(game.start_time)
    if (game.status === 'in_progress') {
      if (game.sport === 'nfl' || game.sport === 'nba') return `Q${game.period} ${game.clock}`
      if (game.sport === 'nhl') return `P${game.period} ${game.clock}`
      if (game.sport === 'mlb') return `${game.period}th`
      if (game.sport === 'soccer') return game.period === 1 ? '1H' : '2H'
    }
    return game.status
  }

  const isLive = (status: string) => status === 'in_progress'

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">All Sports</h1>
          <p className="text-gray-400">
            {summary?.total_live || 0} live games, {summary?.total_today || 0} total today
          </p>
        </div>
        <Button variant="secondary" onClick={handleRefresh} loading={refreshing}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh All
        </Button>
      </div>

      {/* Sport Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {Object.entries(SPORT_CONFIG).map(([key, config]) => {
          const sportData = summary?.sports[key]
          return (
            <Card key={key} className="cursor-pointer hover:bg-dark-hover transition-colors"
                  onClick={() => setExpandedSport(expandedSport === key ? null : key)}>
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 ${config.color} rounded-lg flex items-center justify-center text-xl`}>
                  {config.icon}
                </div>
                <div>
                  <p className="font-medium text-white">{config.name}</p>
                  <p className="text-xs text-gray-400">
                    {sportData?.live || 0} live / {sportData?.today || 0} today
                  </p>
                </div>
              </div>
            </Card>
          )
        })}
      </div>

      {/* Games by Sport */}
      <div className="space-y-4">
        {Object.entries(SPORT_CONFIG).map(([sportKey, config]) => {
          const sportGames = gamesBySport[sportKey] || []
          const isExpanded = expandedSport === sportKey || expandedSport === null
          
          if (sportGames.length === 0) return null
          
          return (
            <Card key={sportKey}>
              <div 
                className="flex items-center justify-between cursor-pointer"
                onClick={() => setExpandedSport(expandedSport === sportKey ? null : sportKey)}
              >
                <div className="flex items-center gap-3">
                  <span className="text-xl">{config.icon}</span>
                  <h3 className="text-lg font-medium text-white">{config.name}</h3>
                  <span className="text-sm text-gray-400">({sportGames.length} games)</span>
                </div>
                {isExpanded ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
              </div>
              
              {isExpanded && (
                <div className="mt-4 space-y-2">
                  {sportGames.map(game => (
                    <div 
                      key={game.id}
                      className={`p-3 rounded-lg cursor-pointer transition-colors ${
                        selectedGame?.id === game.id ? 'bg-accent-blue/20 border border-accent-blue' : 'bg-dark-hover hover:bg-dark-border'
                      }`}
                      onClick={(e) => { e.stopPropagation(); setSelectedGame(selectedGame?.id === game.id ? null : game) }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-gray-400 text-xs w-10">{game.away_team.abbreviation}</span>
                            <span className="text-white">{game.away_team.name}</span>
                            <span className="font-bold text-white ml-auto">{game.away_score}</span>
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-gray-400 text-xs w-10">{game.home_team.abbreviation}</span>
                            <span className="text-white">{game.home_team.name}</span>
                            <span className="font-bold text-white ml-auto">{game.home_score}</span>
                          </div>
                        </div>
                        <div className="ml-4 text-right">
                          <div className={`flex items-center gap-2 ${isLive(game.status) ? 'text-accent-green' : 'text-gray-400'}`}>
                            {isLive(game.status) && <span className="w-2 h-2 bg-accent-green rounded-full animate-pulse" />}
                            <span className="text-sm">{getStatusDisplay(game)}</span>
                          </div>
                          {game.spread && (
                            <span className="text-xs text-gray-500">Spread: {game.spread > 0 ? '+' : ''}{game.spread}</span>
                          )}
                        </div>
                      </div>
                      
                      {/* Expanded Game Details */}
                      {selectedGame?.id === game.id && (
                        <div className="mt-3 pt-3 border-t border-dark-border">
                          <div className="grid grid-cols-2 gap-4 text-sm">
                            <div>
                              <p className="text-gray-400">Venue</p>
                              <p className="text-white">{game.venue || 'TBD'}</p>
                            </div>
                            <div>
                              <p className="text-gray-400">Start Time</p>
                              <p className="text-white">{formatTime(game.start_time)}</p>
                            </div>
                            {game.spread && (
                              <div>
                                <p className="text-gray-400">Spread</p>
                                <p className="text-white">{game.spread > 0 ? '+' : ''}{game.spread}</p>
                              </div>
                            )}
                            {game.has_open_position && (
                              <div>
                                <p className="text-gray-400">Position</p>
                                <p className="text-accent-blue">Open Position</p>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )
        })}
      </div>

      {/* Recent Events */}
      {events && events.length > 0 && (
        <Card>
          <h3 className="text-lg font-medium text-white mb-4">Recent Scoring Events</h3>
          <div className="space-y-2">
            {events.map(event => (
              <div key={event.id} className="flex items-center gap-3 p-2 bg-dark-hover rounded-lg">
                <span className="text-xl">{SPORT_CONFIG[event.sport]?.icon || '🎯'}</span>
                <div className="flex-1">
                  <p className="text-sm text-white">
                    <span className="font-medium">{event.scoring_team}</span>
                    <span className="text-gray-400 mx-2">+{event.points_scored}</span>
                    <span className="text-accent-green">{event.score}</span>
                  </p>
                  <p className="text-xs text-gray-500">
                    {event.scoring_type} • {SPORT_CONFIG[event.sport]?.name}
                  </p>
                </div>
                <span className="text-xs text-gray-500">{formatTime(event.timestamp)}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {loading && games?.length === 0 && (
        <div className="text-center text-gray-400 py-8">Loading games...</div>
      )}
    </div>
  )
}
