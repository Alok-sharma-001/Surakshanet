import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { useTrafficStore } from '../../store/trafficStore';
import clsx from 'clsx';
import { 
  Map, 
  Activity, 
  TrendingUp, 
  Navigation, 
  Bell, 
  Siren, 
  BarChart3, 
  Users 
} from 'lucide-react';

const Sidebar: React.FC = () => {
  const { user } = useAuthStore();
  const alerts = useTrafficStore((state) => state.alerts);
  const unreadAlerts = alerts.filter(a => !a.is_acknowledged).length;

  const navItems = [
    { name: 'Traffic Map', path: '/', icon: Map },
    { name: 'Signal Control', path: '/signals', icon: Activity },
    { name: 'Forecasting', path: '/forecasting', icon: TrendingUp },
    { name: 'Routing', path: '/routing', icon: Navigation },
    { name: 'Alerts', path: '/alerts', icon: Bell, badge: unreadAlerts },
    { name: 'Emergency', path: '/emergency', icon: Siren },
    { name: 'Analytics', path: '/analytics', icon: BarChart3 },
  ];

  if (user?.role === 'ADMIN') {
    navItems.push({ name: 'User Management', path: '/users', icon: Users });
  }

  return (
    <div className="hidden md:flex flex-col w-72 sidebar shadow-lg z-20">
      <div className="flex items-center justify-center h-20 border-b border-slate-700 px-6">
        <div className="flex items-center space-x-3">
          <Siren className="text-blue-500 w-8 h-8" />
          <span className="text-2xl font-bold text-white tracking-tight">Surakshanet</span>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto py-6 flex flex-col gap-2 px-4">
        {navItems.map((item) => (
          <NavLink
            key={item.name}
            to={item.path}
            className={({ isActive }) => clsx(
              'flex items-center justify-between px-4 py-3 rounded-lg transition-colors',
              isActive 
                ? 'bg-blue-600 text-white' 
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
            )}
          >
            <div className="flex items-center space-x-3">
              <item.icon className="w-5 h-5" />
              <span className="font-medium">{item.name}</span>
            </div>
            {item.badge ? (
              <span className="bg-red-500 text-white text-xs font-bold px-2 py-1 rounded-full">
                {item.badge}
              </span>
            ) : null}
          </NavLink>
        ))}
      </div>
      <div className="p-4 border-t border-slate-700">
        <div className="flex items-center space-x-2 text-sm text-slate-400">
          <div className="status-dot bg-green-500"></div>
          <span>System Online</span>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;
