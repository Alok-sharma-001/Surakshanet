import { useState } from 'react';
import { TrendingUp, AlertCircle, BarChart3 } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { clsx } from 'clsx';

const mockData = Array.from({ length: 9 }).map((_, i) => {
  const timeLabels = ['T-45', 'T-30', 'T-15', 'Now', 'T+15', 'T+30', 'T+45', 'T+60', 'T+75'];
  const baseActual = [20, 35, 45, 60, null, null, null, null, null];
  const basePredicted = [20, 36, 43, 60, 78, 85, 92, 88, 80];
  
  return {
    name: timeLabels[i],
    actual: baseActual[i],
    predicted: basePredicted[i],
  };
});

export default function ForecastingPage() {
  const [horizon, setHorizon] = useState<'15' | '30' | '60'>('15');
  const [acknowledged, setAcknowledged] = useState(false);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-syne font-bold text-slate-900">Traffic Forecasting</h1>
          <p className="text-sm text-slate-500 mt-1">Spillback Prediction & Flow Telemetry Model</p>
        </div>

        <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200">
          {(['15', '30', '60'] as const).map(h => (
            <button
              key={h}
              onClick={() => setHorizon(h)}
              className={clsx(
                "px-4 py-2 rounded-md text-sm font-semibold transition-all",
                horizon === h ? "bg-white text-teal-600 outline outline-2 outline-teal-500 shadow-sm z-10" : "text-slate-600 hover:text-slate-900"
              )}
            >
              {h} Min
            </button>
          ))}
        </div>
      </div>

      {/* Alert Banner */}
      {!acknowledged && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start justify-between shadow-sm">
          <div className="flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="text-sm font-bold text-amber-800">High Spillback Risk Detected - Junction A4 (Northbound)</h3>
              <p className="text-sm text-amber-700 mt-1">Predicted queue exceeds 80% capacity within the next 15-minute horizon. Ensemble model confidence: 92%.</p>
            </div>
          </div>
          <button 
            onClick={() => setAcknowledged(true)}
            className="px-4 py-1.5 bg-red-100 text-red-600 hover:bg-red-200 rounded-full text-xs font-bold transition-colors flex-shrink-0"
          >
            Acknowledge
          </button>
        </div>
      )}

      {/* Main Content (2-column grid) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left: Actual vs Predicted PCU chart card */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 h-[400px] flex flex-col">
          <h3 className="text-sm font-semibold text-slate-800 mb-4 flex items-center">
            <TrendingUp className="w-4 h-4 mr-2 text-slate-500" />
            Actual vs Predicted PCU
          </h3>
          <div className="flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={mockData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorActual" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorPredicted" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0d9488" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#0d9488" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                <Legend iconType="circle" />
                <Area type="monotone" dataKey="actual" name="Actual (PCU)" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorActual)" />
                <Area type="monotone" dataKey="predicted" name="Predicted (PCU)" stroke="#0d9488" strokeWidth={2} strokeDasharray="5 5" fillOpacity={1} fill="url(#colorPredicted)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right: Spillback Risk (Kspill) gauge */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 flex flex-col items-center justify-center h-[400px]">
          <h3 className="text-sm font-semibold text-slate-800 mb-6 w-full text-left">Spillback Risk (Kspill)</h3>
          
          <div className="relative w-48 h-24 mb-4">
            <svg viewBox="0 0 200 100" className="w-full h-full overflow-visible">
              <defs>
                <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#10b981" />
                  <stop offset="50%" stopColor="#f59e0b" />
                  <stop offset="100%" stopColor="#ef4444" />
                </linearGradient>
              </defs>
              <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#e2e8f0" strokeWidth="20" strokeLinecap="round" />
              <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="url(#gaugeGradient)" strokeWidth="20" strokeLinecap="round" strokeDasharray="251" strokeDashoffset="45" />
              
              {/* Needle pointing to ~0.82 */}
              <g transform="translate(100, 100) rotate(57)">
                <path d="M -5 0 L 0 -70 L 5 0 Z" fill="#334155" />
                <circle cx="0" cy="0" r="8" fill="#334155" />
              </g>
            </svg>
            <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-2xl font-syne font-bold text-slate-900">0.82</div>
          </div>
          
          <div className="mt-8 text-center">
            <div className="text-red-600 font-bold text-sm bg-red-50 px-3 py-1 rounded-full inline-block">CRITICAL</div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mt-3">Capacity Threshold: 0.75 Limit</div>
          </div>
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Left: Model Weight Contribution */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
          <h3 className="text-sm font-semibold text-slate-800 mb-5 flex items-center">
            <BarChart3 className="w-4 h-4 mr-2 text-slate-500" />
            Model Weight Contribution
          </h3>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm font-medium mb-1.5">
                <span className="text-slate-600">Ensemble (Meta-Model)</span>
                <span className="text-slate-900 font-mono">55%</span>
              </div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-teal-500 rounded-full" style={{ width: '55%' }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm font-medium mb-1.5">
                <span className="text-slate-600">LSTM (Temporal)</span>
                <span className="text-slate-900 font-mono">30%</span>
              </div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-teal-500 rounded-full" style={{ width: '30%' }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm font-medium mb-1.5">
                <span className="text-slate-600">XGBoost (Feature-based)</span>
                <span className="text-slate-900 font-mono">15%</span>
              </div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-teal-500 rounded-full" style={{ width: '15%' }}></div>
              </div>
            </div>
          </div>
        </div>

        {/* Right: MAPE Scores */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
          <h3 className="text-sm font-semibold text-slate-800 mb-5">MAPE Scores (Mean Absolute Percentage Error)</h3>
          <div className="grid grid-cols-3 gap-4 h-[calc(100%-2rem)]">
            <div className="bg-slate-50 rounded-lg p-4 flex flex-col justify-center items-center border border-slate-100">
              <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">15 Min</div>
              <div className="text-2xl font-syne font-bold text-teal-600 mb-1">4.2%</div>
              <div className="text-xs font-bold text-emerald-500">↓ 0.5%</div>
            </div>
            <div className="bg-slate-50 rounded-lg p-4 flex flex-col justify-center items-center border border-slate-100">
              <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">30 Min</div>
              <div className="text-2xl font-syne font-bold text-teal-600 mb-1">7.8%</div>
              <div className="text-xs font-bold text-red-500">↑ 1.2%</div>
            </div>
            <div className="bg-slate-50 rounded-lg p-4 flex flex-col justify-center items-center border border-slate-100">
              <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">60 Min</div>
              <div className="text-2xl font-syne font-bold text-teal-600 mb-1">12.5%</div>
              <div className="text-xs font-bold text-red-500">↑ 3.1%</div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
