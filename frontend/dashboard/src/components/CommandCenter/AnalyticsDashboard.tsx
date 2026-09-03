import React from 'react';
import { 
  AreaChart, 
  Area, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';
import { 
  TrendingDown, 
  TrendingUp, 
  Clock, 
  Zap, 
  ShieldCheck, 
  Gauge
} from 'lucide-react';

const WAIT_TIME_TREND = [
  { time: '08:00', beforeAI: 130, afterAI: 85 },
  { time: '09:00', beforeAI: 168, afterAI: 92 },
  { time: '10:00', beforeAI: 154, afterAI: 88 },
  { time: '11:00', beforeAI: 120, afterAI: 72 },
  { time: '12:00', beforeAI: 110, afterAI: 68 },
  { time: '13:00', beforeAI: 125, afterAI: 74 },
  { time: '14:00', beforeAI: 142, afterAI: 86 },
];

const HOURLY_THROUGHPUT = [
  { hour: '08h', vehicles: 4200, capacity: 5000 },
  { hour: '09h', vehicles: 5800, capacity: 5500 },
  { hour: '10h', vehicles: 5100, capacity: 5500 },
  { hour: '11h', vehicles: 3900, capacity: 5000 },
  { hour: '12h', vehicles: 3400, capacity: 4800 },
  { hour: '13h', vehicles: 4100, capacity: 5000 },
  { hour: '14h', vehicles: 4950, capacity: 5200 },
];

export const AnalyticsDashboard: React.FC = () => {
  return (
    <div className="space-y-6 font-syne">
      {/* Top 4 KPI Banner Cards in White Studio Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 font-grotesk">
        {/* Card 1: Average Wait Time */}
        <div className="bg-white rounded-3xl p-5 border border-studio-pink/40 shadow-studio-card relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-mono text-studio-muted">
            <span>AVERAGE WAIT TIME</span>
            <Clock className="w-4 h-4 text-studio-coral" />
          </div>
          <div className="my-3 flex items-baseline gap-2">
            <span className="text-3xl font-black text-studio-text font-syne">86</span>
            <span className="text-xs text-studio-muted font-mono">SEC / VEHICLE</span>
          </div>
          <div className="pt-2 border-t border-studio-pink/30 flex items-center justify-between text-xs font-mono">
            <span className="text-studio-muted line-through">142s Before AI</span>
            <span className="text-emerald-700 font-bold flex items-center gap-1">
              <TrendingDown className="w-3.5 h-3.5" />
              39.4% IMPROVEMENT
            </span>
          </div>
        </div>

        {/* Card 2: Average Traffic Speed */}
        <div className="bg-white rounded-3xl p-5 border border-studio-pink/40 shadow-studio-card relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-mono text-studio-muted">
            <span>AVG CORRIDOR SPEED</span>
            <Gauge className="w-4 h-4 text-studio-coral" />
          </div>
          <div className="my-3 flex items-baseline gap-2">
            <span className="text-3xl font-black text-studio-coralDark font-syne">38.2</span>
            <span className="text-xs text-studio-muted font-mono">KM/H</span>
          </div>
          <div className="pt-2 border-t border-studio-pink/30 flex items-center justify-between text-xs font-mono">
            <span className="text-studio-muted">22 km/h Baseline</span>
            <span className="text-emerald-700 font-bold flex items-center gap-1">
              <TrendingUp className="w-3.5 h-3.5" />
              +73.6% SPEED
            </span>
          </div>
        </div>

        {/* Card 3: Autonomous AI Interventions */}
        <div className="bg-white rounded-3xl p-5 border border-studio-pink/40 shadow-studio-card relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-mono text-studio-muted">
            <span>AI SIGNAL INTERVENTIONS</span>
            <Zap className="w-4 h-4 text-amber-500" />
          </div>
          <div className="my-3 flex items-baseline gap-2">
            <span className="text-3xl font-black text-studio-text font-syne">1,492</span>
            <span className="text-xs text-studio-muted font-mono">TODAY</span>
          </div>
          <div className="pt-2 border-t border-studio-pink/30 flex items-center justify-between text-xs font-mono">
            <span className="text-studio-muted">100% Conflict-Free</span>
            <span className="text-studio-coral font-bold">12ms LATENCY</span>
          </div>
        </div>

        {/* Card 4: Road Safety & Incident Reduction */}
        <div className="bg-white rounded-3xl p-5 border border-studio-pink/40 shadow-studio-card relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-mono text-studio-muted">
            <span>ACCIDENT RISK REDUCTION</span>
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="my-3 flex items-baseline gap-2">
            <span className="text-3xl font-black text-emerald-600 font-syne">-54.2%</span>
            <span className="text-xs text-studio-muted font-mono">Q3 ESTIMATE</span>
          </div>
          <div className="pt-2 border-t border-studio-pink/30 flex items-center justify-between text-xs font-mono">
            <span className="text-studio-muted">Green Corridors</span>
            <span className="text-emerald-700 font-bold">ACTIVE</span>
          </div>
        </div>
      </div>

      {/* Main Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left 7 cols: Before vs After AI Average Wait Time */}
        <div className="lg:col-span-7 bg-white rounded-3xl p-6 border border-studio-pink/40 shadow-studio-card">
          <div className="flex items-center justify-between pb-4 mb-4 border-b border-studio-pink/30">
            <div>
              <h4 className="text-lg font-bold text-studio-text font-syne">Wait Time Optimization Curve</h4>
              <p className="text-xs font-grotesk text-studio-muted">Comparing Static Webster Timing vs Autonomous MARL Agent (Seconds)</p>
            </div>
            <div className="flex items-center gap-4 text-xs font-grotesk font-semibold">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-slate-400" />
                <span className="text-studio-muted">Before AI</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-studio-coral" />
                <span className="text-studio-coral font-bold">SurakshaNet AI</span>
              </div>
            </div>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={WAIT_TIME_TREND} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorAfterAI" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#E5584D" stopOpacity={0.35}/>
                    <stop offset="95%" stopColor="#E5584D" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorBeforeAI" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#94A3B8" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#94A3B8" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#F5DDD8" />
                <XAxis dataKey="time" stroke="#8A7A78" fontSize={11} fontFamily="JetBrains Mono" />
                <YAxis stroke="#8A7A78" fontSize={11} fontFamily="JetBrains Mono" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#FFFFFF',
                    borderColor: '#F7C6BF',
                    borderRadius: '12px',
                    fontFamily: 'Space Grotesk',
                    fontSize: '12px',
                    boxShadow: '0 10px 25px rgba(229, 88, 77, 0.1)',
                  }}
                />
                <Area type="monotone" dataKey="beforeAI" stroke="#94A3B8" strokeWidth={2} fillOpacity={1} fill="url(#colorBeforeAI)" />
                <Area type="monotone" dataKey="afterAI" stroke="#E5584D" strokeWidth={2.5} fillOpacity={1} fill="url(#colorAfterAI)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right 5 cols: Vehicle Throughput BarChart */}
        <div className="lg:col-span-5 bg-white rounded-3xl p-6 border border-studio-pink/40 shadow-studio-card">
          <div className="flex items-center justify-between pb-4 mb-4 border-b border-studio-pink/30">
            <div>
              <h4 className="text-lg font-bold text-studio-text font-syne">Peak Hour Throughput</h4>
              <p className="text-xs font-grotesk text-studio-muted">Hourly Passenger Car Units (PCU)</p>
            </div>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={HOURLY_THROUGHPUT} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F5DDD8" />
                <XAxis dataKey="hour" stroke="#8A7A78" fontSize={11} fontFamily="JetBrains Mono" />
                <YAxis stroke="#8A7A78" fontSize={11} fontFamily="JetBrains Mono" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#FFFFFF',
                    borderColor: '#F7C6BF',
                    borderRadius: '12px',
                    fontFamily: 'Space Grotesk',
                    fontSize: '12px',
                    boxShadow: '0 10px 25px rgba(229, 88, 77, 0.1)',
                  }}
                />
                <Bar dataKey="vehicles" fill="#0D0E11" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
