import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import clsx from 'clsx';
import {
  LayoutDashboard,
  Network,
  SlidersHorizontal,
  TrendingUp,
  Siren,
  Route,
  BarChart3,
  Leaf,
  Bell,
  Radio,
  Monitor,
  Users,
  Settings,
  LogOut,
  Shield,
} from 'lucide-react';

interface NavItem {
  name: string;
  path: string;
  icon: React.ElementType;
  end?: boolean;
  badge?: number | null;
}

const mainNavItems: NavItem[] = [
  { name: 'Dashboard', path: '/app', icon: LayoutDashboard, end: true },
  { name: 'Junctions', path: '/app/junctions', icon: Network },
  { name: 'Signal Control', path: '/app/signals', icon: SlidersHorizontal },
  { name: 'Forecasting', path: '/app/forecasting', icon: TrendingUp },
  { name: 'Emergency', path: '/app/emergency', icon: Siren, badge: 1 },
  { name: 'Routing', path: '/app/routing', icon: Route },
];

const analyticsNavItems: NavItem[] = [
  { name: 'Analytics', path: '/app/analytics', icon: BarChart3 },
  { name: 'Emissions', path: '/app/emissions', icon: Leaf },
];

const systemNavItems: NavItem[] = [
  { name: 'Alerts', path: '/app/alerts', icon: Bell, badge: 5 },
  { name: 'Edge Devices', path: '/app/edge-devices', icon: Radio },
  { name: 'Simulation', path: '/app/simulation', icon: Monitor },
];

const adminNavItems: NavItem[] = [
  { name: 'Users', path: '/app/users', icon: Users },
  { name: 'Settings', path: '/app/settings', icon: Settings },
];

const NavSection: React.FC<{ items: NavItem[]; label?: string }> = ({ items, label }) => (
  <div className="space-y-0.5">
    {label && (
      <div className="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
        {label}
      </div>
    )}
    {items.map((item) => (
      <NavLink
        key={item.path}
        to={item.path}
        end={item.end}
        className={({ isActive }) =>
          clsx(
            'flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-all group relative',
            isActive
              ? 'bg-teal-50 text-teal-700 font-semibold'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          )
        }
      >
        {({ isActive }) => (
          <>
            {/* Active indicator bar */}
            {isActive && (
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-teal-500 rounded-r-full" />
            )}
            <item.icon
              className={clsx(
                'w-[18px] h-[18px] flex-shrink-0',
                isActive ? 'text-teal-600' : 'text-slate-400 group-hover:text-slate-600'
              )}
            />
            <span className="flex-1">{item.name}</span>
            {item.badge != null && item.badge > 0 && (
              <span
                className={clsx(
                  'min-w-[18px] h-[18px] flex items-center justify-center rounded-full text-[10px] font-bold',
                  isActive
                    ? 'bg-teal-600 text-white'
                    : 'bg-red-500 text-white'
                )}
              >
                {item.badge}
              </span>
            )}
          </>
        )}
      </NavLink>
    ))}
  </div>
);

const Sidebar: React.FC = () => {
  const { logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside className="hidden md:flex flex-col w-[240px] bg-white border-r border-slate-200 h-screen flex-shrink-0 font-sans select-none">
      {/* Logo / Branding */}
      <div className="px-4 py-4 border-b border-slate-100">
        <div
          onClick={() => navigate('/app')}
          className="flex items-center gap-2.5 cursor-pointer group"
        >
          <div className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-200 flex items-center justify-center group-hover:scale-105 transition-transform shadow-sm">
            <Shield className="w-4 h-4 text-teal-600" />
          </div>
          <div>
            <h1 className="text-[15px] font-bold text-slate-900 leading-tight">Surakshanet</h1>
            <p className="text-[10px] text-slate-400 font-medium">Traffic Ops Center</p>
          </div>
        </div>
      </div>

      {/* System Health Badge */}
      <div className="px-4 py-2.5">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 border border-emerald-200 rounded-lg">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-40" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          <span className="text-[11px] font-semibold text-emerald-700">System Health: Optimal</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-1 space-y-3">
        <NavSection items={mainNavItems} />
        
        <div className="border-t border-slate-100 pt-2">
          <NavSection items={analyticsNavItems} label="Insights" />
        </div>

        <div className="border-t border-slate-100 pt-2">
          <NavSection items={systemNavItems} label="System" />
        </div>

        <div className="border-t border-slate-100 pt-2">
          <NavSection items={adminNavItems} label="Admin" />
        </div>
      </nav>

      {/* Logout */}
      <div className="px-3 py-3 border-t border-slate-100">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium w-full text-slate-500 hover:text-red-600 hover:bg-red-50 transition-colors"
        >
          <LogOut className="w-[18px] h-[18px]" />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
