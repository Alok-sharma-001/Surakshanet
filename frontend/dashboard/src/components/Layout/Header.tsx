import React from 'react';
import { useLocation } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { useTrafficStore } from '../../store/trafficStore';
import { Bell, LogOut, Play, Square } from 'lucide-react';

const getPageTitle = (pathname: string) => {
  if (pathname === '/') return 'Traffic Map';
  const routes: Record<string, string> = {
    '/signals': 'Signal Control',
    '/forecasting': 'Forecasting',
    '/routing': 'Routing',
    '/alerts': 'Alerts',
    '/emergency': 'Emergency',
    '/analytics': 'Analytics',
    '/users': 'User Management',
  };
  for (const route in routes) {
    if (pathname.startsWith(route)) return routes[route];
  }
  return 'Dashboard';
};

const Header: React.FC = () => {
  const { user, logout } = useAuthStore();
  const location = useLocation();
  const title = getPageTitle(location.pathname);
  
  const alerts = useTrafficStore((state) => state.alerts);
  const unreadCount = alerts.filter(a => !a.is_acknowledged).length;
  const isSimulationRunning = useTrafficStore((state) => state.isSimulationRunning);

  const getInitials = (name: string) => {
    return name.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2);
  };

  return (
    <header className="h-20 bg-white shadow-sm border-b border-gray-200 flex items-center justify-between px-6 z-10 relative">
      <div className="flex items-center space-x-6">
        <h1 className="text-2xl font-bold text-gray-800">{title}</h1>
        <div className="hidden sm:flex items-center space-x-2 bg-gray-100 rounded-full px-3 py-1">
          {isSimulationRunning ? (
            <><Play className="w-4 h-4 text-green-500" /> <span className="text-sm font-medium text-gray-600">Sim Running</span></>
          ) : (
            <><Square className="w-4 h-4 text-gray-400" /> <span className="text-sm font-medium text-gray-500">Sim Stopped</span></>
          )}
        </div>
      </div>
      
      <div className="flex items-center space-x-6">
        <button className="relative p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-full transition-colors">
          <Bell className="w-6 h-6" />
          {unreadCount > 0 && (
            <span className="absolute top-0 right-0 inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-red-500 border-2 border-white rounded-full">
              {unreadCount}
            </span>
          )}
        </button>
        
        <div className="flex items-center space-x-3 border-l border-gray-200 pl-6">
          <div className="flex flex-col items-end">
            <span className="text-sm font-bold text-gray-800">{user?.name}</span>
            <span className="text-xs font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded">{user?.role}</span>
          </div>
          <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold">
            {user?.name ? getInitials(user.name) : 'U'}
          </div>
          <button 
            onClick={logout}
            className="ml-2 p-2 text-gray-400 hover:text-red-500 rounded-full hover:bg-red-50 transition-colors"
            title="Logout"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
