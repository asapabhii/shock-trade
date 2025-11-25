import { cn } from '../lib/utils'

interface CardProps {
  children: React.ReactNode
  className?: string
  hover?: boolean
  onClick?: () => void
}

export function Card({ children, className, hover = false, onClick }: CardProps) {
  return (
    <div
      className={cn(
        'bg-dark-card border border-dark-border rounded-xl p-6',
        hover && 'card-hover cursor-pointer',
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
    >
      {children}
    </div>
  )
}

interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  trend?: 'up' | 'down' | 'neutral'
  icon?: React.ReactNode
}

export function StatCard({ title, value, subtitle, trend, icon }: StatCardProps) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-400 mb-1">{title}</p>
          <p
            className={cn(
              'text-2xl font-bold',
              trend === 'up' && 'text-accent-green',
              trend === 'down' && 'text-accent-red',
              !trend && 'text-white'
            )}
          >
            {value}
          </p>
          {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
        </div>
        {icon && (
          <div className="w-10 h-10 bg-dark-hover rounded-lg flex items-center justify-center text-gray-400">
            {icon}
          </div>
        )}
      </div>
    </Card>
  )
}
