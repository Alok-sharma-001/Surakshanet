import { useState, useEffect } from 'react';
import { Grid, ChevronDown, Play, Plus, Minus, AlertTriangle, Shield, Radio } from 'lucide-react';
import { Area, AreaChart, ResponsiveContainer, Tooltip } from 'recharts';
import { toast } from 'react-hot-toast';
import { clsx } from 'clsx';

const mockRewardData = Array.from({ length: 20 }).map((_, i) => ({
  time: i,
  reward: 5 + Math.random() * 10 + Math.sin(i / 2) * 5,
}));

export default function SignalControlPage() {
  const [activeControl, setActiveControl] = useState<'marl' | 'webster' | 'manual'>('marl');
  const [telemetry, setTelemetry] = useState<string[]>([
    "[T-15.2s] State Evaluated Queue: 38veh\n→ ACTION: Maintain Phase 1",
    "[T-12.0s] Reward Calculated    Prev Action: Ph1+2s\nΣ REWARD: +14.2 (Delay Reduced)",
    "[T-4.5s] Phase Transition Current: Ph1\n⏱ ACTION: Trigger Amber (3.0s)\nConstraint: MinGreen Met",
    "[T-0.1s] State Evaluated Queue: 42veh\n→ ACTION: Extend Phase 2 (N-S Straight) by 5.0s\nQ-Value: 0.892  Conf: 92%"
  ]);

  useEffect(() => {
    if (activeControl !== 'marl') return;
    
    const interval = setInterval(() => {
      const q = Math.floor(Math.random() * 50) + 10;
      const act = Math.random() > 0.5 ? 'Maintain Phase 2' : 'Trigger Amber (3.0s)';
      const newEntry = `[T+${(Math.random()*2).toFixed(1)}s] State Evaluated Queue: ${q}veh\n→ ACTION: ${act}\nQ-Value: ${(Math.random()*0.9+0.1).toFixed(3)} Conf: ${Math.floor(Math.random()*15+85)}%`;
      
      setTelemetry(prev => {
        const next = [newEntry, ...prev];
        if (next.length > 20) next.pop();
        return next;
      });
    }, 3000);
    
    return () => clearInterval(interval);
  }, [activeControl]);

  const handleOverride = (action: string) => {
    toast.success(`Action Executed: ${action}`);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-slate-100 rounded-lg">
            <Grid className="w-5 h-5 text-slate-600" />
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Target Node</div>
            <button className="flex items-center space-x-2 text-lg font-syne font-bold text-slate-900 hover:text-slate-700 transition-colors">
              <span>Junction Alpha-9 (Downtown)</span>
              <ChevronDown className="w-4 h-4 text-slate-400" />
            </button>
          </div>
        </div>

        <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200">
          <button
            onClick={() => setActiveControl('marl')}
            className={clsx(
              "px-4 py-2 rounded-md text-sm font-semibold transition-all flex items-center space-x-2",
              activeControl === 'marl' ? "bg-teal-50 text-teal-600 shadow-sm" : "text-slate-600 hover:text-slate-900"
            )}
          >
            {activeControl === 'marl' && <div className="w-2 h-2 rounded-full bg-teal-500 animate-pulse" />}
            <span>MARL Dynamic AI</span>
          </button>
          <button
            onClick={() => setActiveControl('webster')}
            className={clsx(
              "px-4 py-2 rounded-md text-sm font-semibold transition-all",
              activeControl === 'webster' ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
            )}
          >
            Webster (Static)
          </button>
          <button
            onClick={() => setActiveControl('manual')}
            className={clsx(
              "px-4 py-2 rounded-md text-sm font-semibold transition-all",
              activeControl === 'manual' ? "bg-red-50 text-red-600 shadow-sm" : "text-slate-600 hover:text-slate-900"
            )}
          >
            Manual Control
          </button>
        </div>
      </div>

      {/* Main 3-column grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column — Agent Telemetry Stream */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm flex flex-col h-[600px]">
          <div className="p-4 border-b border-[#E2E8F0] flex justify-between items-center bg-slate-50/50 rounded-t-xl">
            <h3 className="text-sm font-semibold text-slate-800 flex items-center">
              <Radio className="w-4 h-4 mr-2 text-teal-500" />
              Agent Telemetry Stream
            </h3>
            <span className="text-xs font-mono bg-slate-100 text-slate-500 px-2 py-1 rounded">Update: 10hz</span>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4 font-mono text-xs text-slate-600 bg-slate-900">
            {telemetry.map((log, idx) => (
              <div key={idx} className={clsx("pb-4 border-b border-slate-800", idx === 0 && "text-teal-400")}>
                {log.split('\n').map((line, i) => (
                  <div key={i} className={clsx(line.startsWith('→') || line.startsWith('⏱') ? "pl-4 text-emerald-400" : "")}>
                    {line}
                  </div>
                ))}
              </div>
            ))}
            <div className="text-slate-500 text-center italic mt-4">-- End of recent buffer --</div>
          </div>
        </div>

        {/* Center Column — Charts */}
        <div className="space-y-6 flex flex-col justify-between h-[600px]">
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 flex-1 flex flex-col">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-800">Instantaneous Reward</h3>
                <div className="text-3xl font-syne font-bold text-teal-600 mt-1">+14.2</div>
              </div>
              <div className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-500">
                ↗ 12% vs avg
              </div>
            </div>
            <div className="flex-1 min-h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={mockRewardData}>
                  <defs>
                    <linearGradient id="colorReward" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0d9488" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#0d9488" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                  <Area type="monotone" dataKey="reward" stroke="#0d9488" strokeWidth={2} fillOpacity={1} fill="url(#colorReward)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
              <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Cumulative Episode Reward</h3>
              <div className="text-2xl font-syne font-bold text-slate-900">1,248</div>
              <div className="text-sm font-mono text-slate-400 mt-1">Episode: 4,092 steps</div>
            </div>
            <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
              <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Delay vs Baseline (Webster)</h3>
              <div className="text-2xl font-syne font-bold text-teal-600">-24.5%</div>
              <div className="text-sm font-mono text-slate-400 mt-1">Avg vehicle delay: 18.2s</div>
            </div>
          </div>
        </div>

        {/* Right Column — Safety & Controls */}
        <div className="space-y-6 flex flex-col h-[600px]">
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
            <h3 className="text-sm font-semibold text-slate-800 flex items-center mb-4">
              <Shield className="w-4 h-4 mr-2 text-slate-500" />
              Safety Guardrails
            </h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium text-slate-600">Min Green Time (12s)</span>
                <span className="flex items-center text-xs font-bold text-emerald-500">Valid <div className="w-2 h-2 rounded-full bg-emerald-500 ml-2"></div></span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium text-slate-600">Amber Interval (3s)</span>
                <span className="flex items-center text-xs font-bold text-emerald-500">Valid <div className="w-2 h-2 rounded-full bg-emerald-500 ml-2"></div></span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium text-slate-600">All-Red Clearance (2s)</span>
                <span className="flex items-center text-xs font-bold text-emerald-500">Valid <div className="w-2 h-2 rounded-full bg-emerald-500 ml-2"></div></span>
              </div>
              <div className="pt-4 border-t border-slate-100 flex justify-between items-center">
                <span className="text-sm font-medium text-slate-600">Conflict Monitor</span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-teal-50 text-teal-600">ONLINE</span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-red-200 shadow-sm p-5 flex-1 flex flex-col">
            <h3 className="text-sm font-semibold text-red-600 flex items-center mb-4 uppercase tracking-wider">
              <AlertTriangle className="w-4 h-4 mr-2" />
              Manual Override Console
            </h3>
            
            <div className="space-y-4 flex-1 flex flex-col">
              <button 
                onClick={() => handleOverride("Force Phase Skip")}
                className="w-full flex items-center justify-center space-x-2 py-3 px-4 border border-slate-300 rounded-lg text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
              >
                <Play className="w-4 h-4" />
                <span>Force Phase Skip</span>
              </button>

              <div className="flex space-x-4">
                <button 
                  onClick={() => handleOverride("+5s Green")}
                  className="flex-1 flex items-center justify-center space-x-2 py-3 px-4 bg-slate-100 rounded-lg text-sm font-semibold text-slate-700 hover:bg-slate-200 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  <span>5s Green</span>
                </button>
                <button 
                  onClick={() => handleOverride("-5s Green")}
                  className="flex-1 flex items-center justify-center space-x-2 py-3 px-4 bg-slate-100 rounded-lg text-sm font-semibold text-slate-700 hover:bg-slate-200 transition-colors"
                >
                  <Minus className="w-4 h-4" />
                  <span>5s Green</span>
                </button>
              </div>

              <div className="flex-1"></div>

              <button 
                onClick={() => handleOverride("ALL RED FLASH INITIATED")}
                className="w-full flex items-center justify-center space-x-2 py-4 px-4 bg-red-500 hover:bg-red-600 text-white rounded-lg font-bold transition-colors shadow-sm"
              >
                <AlertTriangle className="w-5 h-5" />
                <span>ALL RED (FLASH)</span>
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
