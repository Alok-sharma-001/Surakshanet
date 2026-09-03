import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import GlobalEmergencyModal from '../CommandCenter/GlobalEmergencyModal';
import {
  Search,
  Bell,
  Clock,
  AlertTriangle,
  User,
  LogOut,
  Settings,
  ChevronDown,
} from 'lucide-react';
import clsx from 'clsx';

const topNavTabs = [
  { label: 'Network Map', path: '/app' },
  { label: 'Analytics', path: '/app/analytics' },
  { label: 'Reports', path: '/app/analytics' },
];

const Header: React.FC = () => {
  const { user, logout } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();
  const [emergencyOpen, setEmergencyOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [clock, setClock] = useState('');

  // Live clock
  useEffect(() => {
    const tick = () =>
      setClock(
        new Date().toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        })
      );
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const isTabActive = (path: string) => {
    if (path === '/app') return location.pathname === '/app' || location.pathname === '/app/' || location.pathname === '/app/dashboard';
    return location.pathname.startsWith(path);
  };

  return (
    <>
      <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-5 z-30 flex-shrink-0 font-sans">
        {/* Left: Brand + Nav Tabs */}
        <div className="flex items-center gap-6">
          <h2 className="text-base font-bold text-slate-900 whitespace-nowrap tracking-tight">
            Surakshanet <span className="text-teal-600">Ops</span>
          </h2>

          <nav className="hidden lg:flex items-center gap-0.5">
            {topNavTabs.map((tab) => (
              <button
                key={tab.label}
                onClick={() => navigate(tab.path)}
                className={clsx(
                  'px-3 py-1.5 text-xs font-medium rounded-lg transition-all',
                  isTabActive(tab.path)
                    ? 'text-teal-700 bg-teal-50 font-bold border border-teal-200/60'
                    : 'text-slate-500 hover:text-teal-600 hover:bg-slate-50'
                )}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Center: Search */}
        <div className="hidden md:flex items-center flex-1 max-w-sm mx-6">
          <div className="relative w-full">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search entity..."
              className="w-full pl-9 pr-4 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg
                         placeholder:text-slate-400 focus:bg-white focus:ring-2 focus:ring-teal-500/20 
                         focus:border-teal-500 outline-none transition-all"
            />
          </div>
        </div>

        {/* Right: Emergency Override + Icons + Avatar */}
        <div className="flex items-center gap-2">
          {/* Emergency Override Button */}
          <button
            onClick={() => setEmergencyOpen(true)}
            className="hidden sm:inline-flex items-center gap-2 px-3.5 py-1.5 bg-red-500 text-white text-xs 
                       font-bold rounded-lg hover:bg-red-600 transition-colors shadow-sm"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Emergency Override</span>
          </button>

          {/* Notification Bell */}
          <button className="relative p-2 text-slate-400 hover:text-teal-600 hover:bg-teal-50 rounded-lg transition-colors">
            <Bell className="w-4 h-4" />
            <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-red-500 rounded-full" />
          </button>

          {/* Clock */}
          <div className="hidden lg:flex items-center gap-1.5 px-2 py-1 text-xs font-mono text-slate-500">
            <Clock className="w-3.5 h-3.5" />
            <span>{clock}</span>
          </div>

          {/* User Avatar Dropdown */}
          <div className="relative">
            <button
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              className="flex items-center gap-2 p-1 rounded-lg hover:bg-slate-50 transition-colors"
            >
              <div className="w-7 h-7 rounded-full bg-teal-100 border border-teal-200 flex items-center justify-center">
                <User className="w-3.5 h-3.5 text-teal-600" />
              </div>
              <ChevronDown className="w-3 h-3 text-slate-400 hidden sm:block" />
            </button>

            {userMenuOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setUserMenuOpen(false)} />
                <div className="absolute right-0 top-full mt-1 w-52 bg-white rounded-xl border border-slate-200 shadow-lg z-50 py-1.5 overflow-hidden">
                  <div className="px-3.5 py-2.5 border-b border-slate-100">
                    <p className="text-sm font-semibold text-slate-800">{user?.name || 'Operator'}</p>
                    <p className="text-xs text-slate-400 font-mono">{user?.role || 'ADMIN'}</p>
                  </div>
                  <button
                    onClick={() => { setUserMenuOpen(false); navigate('/app/settings'); }}
                    className="flex items-center gap-2.5 w-full px-3.5 py-2 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
                  >
                    <Settings className="w-4 h-4 text-slate-400" />
                    Settings
                  </button>
                  <button
                    onClick={() => { setUserMenuOpen(false); logout(); navigate('/login'); }}
                    className="flex items-center gap-2.5 w-full px-3.5 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <LogOut className="w-4 h-4" />
                    Logout
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Global Emergency Modal */}
      <GlobalEmergencyModal isOpen={emergencyOpen} onClose={() => setEmergencyOpen(false)} />
    </>
  );
};

export default Header;
