import { Outlet, NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  TrendingUp,
  Wallet,
  Settings,
  Activity,
  Gamepad2,
} from 'lucide-react'
import { cn } from '../lib/utils'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/sports', icon: Gamepad2, label: 'All Sports' },
  { to: '/trades', icon: TrendingUp, label: 'Trades' },
  { to: '/positions', icon: Wallet, label: 'Positions' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Layout() {
  return (
    <div className="flex h-screen bg-dark-bg">
      {/* Sidebar */}
      <aside className="w-64 bg-dark-card border-r border-dark-border flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-dark-border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-accent-green rounded-lg flex items-center justify-center">
              <Activity className="w-6 h-6 text-dark-bg" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">ShockTrade</h1>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4">
          <ul className="space-y-2">
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 px-4 py-3 rounded-lg transition-colors',
                      isActive
                        ? 'bg-accent-blue/10 text-accent-blue'
                        : 'text-gray-400 hover:bg-dark-hover hover:text-white'
                    )
                  }
                >
                  <item.icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-dark-border">
          <p className="text-xs text-gray-500 text-center">
            Multi-Sport Trading
          </p>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
