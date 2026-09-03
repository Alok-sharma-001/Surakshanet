import React, { useState } from 'react';
import { 
  Bell, 
  Map, 
  Camera, 
  SlidersHorizontal, 
  AlertTriangle, 
  BarChart3, 
  Layers,
  ArrowUpRight
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export type CommandTab = 'overview' | 'live-map' | 'traffic-ai' | 'signal-control' | 'incidents' | 'analytics';

interface Props {
  activeTab: CommandTab;
  onTabChange: (tab: CommandTab) => void;
}

export const Navbar: React.FC<Props> = ({ activeTab, onTabChange }) => {
  const navigate = useNavigate();
  const [showNotifications, setShowNotifications] = useState(false);

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Layers },
    { id: 'live-map', label: 'Live Map', icon: Map },
    { id: 'traffic-ai', label: 'Traffic AI', icon: Camera },
    { id: 'signal-control', label: 'Signal Control', icon: SlidersHorizontal },
    { id: 'incidents', label: 'Incidents', icon: AlertTriangle, badge: '2' },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
  ];

  return (
    <header className="sticky top-0 z-50 w-full bg-white/85 backdrop-blur-xl border-b border-studio-pink/40 shadow-sm font-syne">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
        {/* Left: Brand Logo & Title matching Studio aesthetic */}
        <div className="flex items-center gap-6">
          <div 
            onClick={() => navigate('/')}
            className="flex items-center gap-3 cursor-pointer group"
          >
            <div className="w-10 h-10 rounded-2xl bg-studio-black shadow-orb flex items-center justify-center group-hover:scale-105 transition-transform">
              <span className="text-studio-coral text-lg font-serif">✻</span>
            </div>
            <div>
              <div className="text-lg font-black tracking-tight text-studio-text leading-tight">
                Suraksha <span className="font-extrabold text-studio-coralDark">One.Zer°</span>
              </div>
              <div className="text-[10px] font-grotesk text-studio-muted tracking-wider uppercase font-semibold">
                INTELLIGENT MOBILITY OPS
              </div>
            </div>
          </div>
        </div>

        {/* Center: Command Center Tabs in rounded pill track */}
        <nav className="hidden md:flex items-center gap-1 bg-studio-bgLight/80 p-1.5 rounded-full border border-studio-pink/40 font-grotesk">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id as CommandTab)}
                className={`relative px-4 py-2 rounded-full text-xs font-bold tracking-wide transition-all flex items-center gap-2 ${
                  isActive
                    ? 'bg-white text-studio-coralDark shadow-sm font-extrabold border border-studio-pink/40'
                    : 'text-studio-text/70 hover:text-studio-coral hover:bg-white/60'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-studio-coral' : ''}`} />
                <span>{tab.label}</span>
                {tab.badge && (
                  <span className="px-1.5 py-0.2 rounded-full text-[9px] bg-studio-coral text-white font-bold animate-pulse">
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Right: Telemetry Status, Notifications, & Profile */}
        <div className="flex items-center gap-4">
          {/* System Online Indicator in Studio styling */}
          <div className="hidden lg:flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-50 border border-emerald-200">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
            <span className="text-[10px] font-mono font-bold text-emerald-700 tracking-wider uppercase">
              SYSTEM ONLINE
            </span>
          </div>

          {/* View Studio Landing Switcher */}
          <button
            onClick={() => navigate('/')}
            className="hidden sm:flex items-center gap-1 text-xs font-grotesk font-semibold text-studio-text/70 hover:text-studio-coral transition-colors"
          >
            <span>Studio</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>

          {/* Notifications Drawer Toggle */}
          <div className="relative">
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="relative p-2.5 rounded-full bg-white border border-studio-pink/40 text-studio-text hover:text-studio-coral hover:border-studio-coral/40 transition-all shadow-sm"
            >
              <Bell className="w-4 h-4" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-studio-coral animate-pulse" />
            </button>

            {showNotifications && (
              <div className="absolute right-0 mt-2 w-80 bg-white p-4 rounded-2xl border border-studio-pink/40 shadow-xl z-50 animate-in fade-in slide-in-from-top-2 duration-200 font-grotesk">
                <div className="text-xs font-mono font-bold text-studio-coralDark uppercase tracking-wider pb-2 border-b border-studio-pink/20">
                  Real-Time Incident Notifications
                </div>
                <div className="space-y-3 mt-3 text-xs">
                  <div className="p-3 rounded-xl bg-red-50 border border-red-200">
                    <div className="font-bold text-red-800">Accident on NH-52</div>
                    <div className="text-slate-600 text-[11px]">Intersection 08 · Ambulances routed</div>
                  </div>
                  <div className="p-3 rounded-xl bg-amber-50 border border-amber-200">
                    <div className="font-bold text-amber-800">Congestion Spike: Lane 01</div>
                    <div className="text-slate-600 text-[11px]">A-102 Signal extended by 18s</div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* User Profile */}
          <div className="flex items-center gap-2.5 pl-2 border-l border-studio-pink/30">
            <div className="w-9 h-9 rounded-full bg-studio-black text-white shadow-orb flex items-center justify-center font-bold text-xs">
              OP
            </div>
            <div className="hidden xl:block text-left font-grotesk">
              <div className="text-xs font-bold text-studio-text">Commander Sharma</div>
              <div className="text-[10px] font-mono text-studio-coral font-semibold">AUTH: LEVEL-4</div>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Tab Bar */}
      <div className="md:hidden flex items-center justify-around border-t border-studio-pink/30 px-2 py-2 overflow-x-auto bg-white">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id as CommandTab)}
            className={`px-3 py-1.5 rounded-full text-xs font-grotesk whitespace-nowrap ${
              activeTab === tab.id
                ? 'bg-studio-coral text-white font-bold'
                : 'text-studio-text/70'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </header>
  );
};
