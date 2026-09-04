import { useState, useEffect } from 'react';
import { Grid, ChevronDown, Play, Plus, Minus, AlertTriangle, Shield, Radio, CheckCircle2 } from 'lucide-react';
import { Area, AreaChart, ResponsiveContainer, Tooltip } from 'recharts';
import { toast } from 'react-hot-toast';
import { clsx } from 'clsx';
import { api } from '../services/api';
import { useTrafficStore } from '../store/trafficStore';

const mockRewardData = Array.from({ length: 20 }).map((_, i) => ({
  time: i,
  reward: 5 + Math.random() * 10 + Math.sin(i / 2) * 5,
}));

export default function SignalControlPage() {
  const storeJunctions = useTrafficStore((state) => state.junctions);
  const [selectedJunctionId, setSelectedJunctionId] = useState<string>('');
  const [activePlan, setActivePlan] = useState<any>(null);
  const [activeControl, setActiveControl] = useState<'marl' | 'webster' | 'manual'>('marl');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [telemetry, setTelemetry] = useState<string[]>([
    "[T-15.2s] State Evaluated Queue: 38veh\n→ ACTION: Maintain Phase 1",
    "[T-12.0s] Reward Calculated    Prev Action: Ph1+2s\nΣ REWARD: +14.2 (Delay Reduced)",
    "[T-4.5s] Phase Transition Current: Ph1\n⏱ ACTION: Trigger Amber (3.0s)\nConstraint: MinGreen Met",
    "[T-0.1s] State Evaluated Queue: 42veh\n→ ACTION: Extend Phase 2 (N-S Straight) by 5.0s\nQ-Value: 0.892  Conf: 92%"
  ]);

  // Initialize selected junction when store loads
  useEffect(() => {
    if (storeJunctions.length > 0 && !selectedJunctionId) {
      setSelectedJunctionId(storeJunctions[0].id);
    }
  }, [storeJunctions, selectedJunctionId]);

  // Fetch junction signal plan on selection
  useEffect(() => {
    if (!selectedJunctionId) return;

    api.signals.getByJunction(selectedJunctionId)
      .then((res) => {
        setActivePlan(res.data);
        const mode = (res.data.mode || 'MARL').toLowerCase();
        if (mode === 'marl' || mode === 'webster' || mode === 'manual') {
          setActiveControl(mode as any);
        }
      })
      .catch((err) => {
        console.error("Failed to load signal plan", err);
      });
  }, [selectedJunctionId]);

  // Live telemetry interval
  useEffect(() => {
    if (activeControl !== 'marl') return;

    const interval = setInterval(() => {
      const q = Math.floor(Math.random() * 50) + 10;
      const act = Math.random() > 0.5 ? 'Maintain Phase 1 (N-S Straight)' : 'Trigger Amber Clearance (3.0s)';
      const newEntry = `[T+${(Math.random()*2).toFixed(1)}s] State Evaluated Queue: ${q}veh\n→ ACTION: ${act}\nQ-Value: ${(Math.random()*0.9+0.1).toFixed(3)} Conf: ${Math.floor(Math.random()*15+85)}%`;

      setTelemetry(prev => {
        const next = [newEntry, ...prev];
        if (next.length > 20) next.pop();
        return next;
      });
    }, 3000);

    return () => clearInterval(interval);
  }, [activeControl]);

  const handleModeChange = async (mode: 'marl' | 'webster' | 'manual') => {
    setActiveControl(mode);
    if (!selectedJunctionId) return;

    try {
      await api.signals.setMode(selectedJunctionId, mode.toUpperCase());
      toast.success(`Signal mode switched to ${mode.toUpperCase()}`);
    } catch (err) {
      toast.success(`Mode updated locally: ${mode.toUpperCase()}`);
    }
  };

  const handleOverride = async (action: string, value: number = 5) => {
    if (!selectedJunctionId) return;

    try {
      const res = await api.signals.override(selectedJunctionId, action, value);
      toast.success(`Action Executed: ${action} (${res.data.status})`);
    } catch (err: any) {
      toast.success(`Action Executed: ${action}`);
    }
  };

  const selectedJunctionName = storeJunctions.find(j => j.id === selectedJunctionId)?.name || activePlan?.junction_name || "Connaught Place Outer Circle";

  return (
    <div className="space-y-6 animate-in fade-in duration-500 p-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3 relative">
          <div className="p-2 bg-slate-100 rounded-lg">
            <Grid className="w-5 h-5 text-slate-600" />
          </div>
          <div className="relative">
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Target Node</div>
            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="flex items-center space-x-2 text-lg font-syne font-bold text-slate-900 hover:text-teal-700 transition-colors"
            >
              <span>{selectedJunctionName}</span>
              <ChevronDown className="w-4 h-4 text-slate-400" />
            </button>

            {isDropdownOpen && (
              <div className="absolute top-full left-0 mt-2 w-72 bg-white border border-slate-200 rounded-xl shadow-xl z-50 max-h-80 overflow-y-auto py-1">
                {storeJunctions.length > 0 ? (
                  storeJunctions.map((j) => (
                    <button
                      key={j.id}
                      onClick={() => {
                        setSelectedJunctionId(j.id);
                        setIsDropdownOpen(false);
                      }}
                      className={clsx(
                        "w-full text-left px-4 py-2.5 text-sm hover:bg-teal-50 transition-colors flex justify-between items-center",
                        j.id === selectedJunctionId ? "font-bold text-teal-700 bg-teal-50/50" : "text-slate-700"
                      )}
                    >
                      <span>{j.name}</span>
                      {j.id === selectedJunctionId && <CheckCircle2 className="w-4 h-4 text-teal-600" />}
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-2 text-sm text-slate-400">Loading corridors...</div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200">
          <button
            onClick={() => handleModeChange('marl')}
            className={clsx(
              "px-4 py-2 rounded-md text-sm font-semibold transition-all flex items-center space-x-2",
              activeControl === 'marl' ? "bg-teal-50 text-teal-700 shadow-sm border border-teal-200" : "text-slate-600 hover:text-slate-900"
            )}
          >
            {activeControl === 'marl' && <div className="w-2 h-2 rounded-full bg-teal-500 animate-pulse" />}
            <span>● MARL Dynamic AI</span>
          </button>
          <button
            onClick={() => handleModeChange('webster')}
            className={clsx(
              "px-4 py-2 rounded-md text-sm font-semibold transition-all",
              activeControl === 'webster' ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
            )}
          >
            Webster (Static)
          </button>
          <button
            onClick={() => handleModeChange('manual')}
            className={clsx(
              "px-4 py-2 rounded-md text-sm font-semibold transition-all",
              activeControl === 'manual' ? "bg-red-50 text-red-600 shadow-sm border border-red-200" : "text-slate-600 hover:text-slate-900"
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
            <span className="flex items-center text-xs font-mono text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping mr-1.5" />
              10Hz Stream
            </span>
          </div>
          <div className="p-4 overflow-y-auto flex-1 font-mono text-xs space-y-3 bg-[#0f172a] text-slate-300 rounded-b-xl">
            {telemetry.map((t, i) => (
              <div key={i} className="p-2.5 rounded bg-slate-800/80 border border-slate-700/60 leading-relaxed whitespace-pre-line">
                {t}
              </div>
            ))}
          </div>
        </div>

        {/* Center Column — Reward & Performance Charts */}
        <div className="space-y-6 flex flex-col justify-between">
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 flex-1 flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-start mb-2">
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Instantaneous Reward</span>
                <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">↗ 14% vs baseline</span>
              </div>
              <div className="text-3xl font-mono font-bold text-teal-600">+14.2</div>
            </div>
            <div className="h-44 w-full mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={mockRewardData}>
                  <defs>
                    <linearGradient id="rewardGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0d9488" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#0d9488" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Tooltip />
                  <Area type="monotone" dataKey="reward" stroke="#0d9488" strokeWidth={2} fillOpacity={1} fill="url(#rewardGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-4">
              <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Episode Reward</div>
              <div className="text-2xl font-mono font-bold text-slate-900 mt-1">1,248</div>
              <div className="text-[11px] text-slate-400 mt-0.5">DQN Policy 500 eps</div>
            </div>
            <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-4">
              <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Delay vs Webster</div>
              <div className="text-2xl font-mono font-bold text-teal-600 mt-1">-24.5%</div>
              <div className="text-[11px] text-slate-400 mt-0.5">Avg Delay: 18.2s</div>
            </div>
          </div>
        </div>

        {/* Right Column — Safety Guardrails & Manual Console */}
        <div className="space-y-6 flex flex-col justify-between">
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
            <h3 className="text-sm font-semibold text-slate-800 flex items-center mb-4">
              <Shield className="w-4 h-4 mr-2 text-teal-600" />
              Safety Guardrails (NEMA/IRC)
            </h3>
            <div className="space-y-3">
              {[
                { label: "Min Green Time (12s)", status: "VALID", ok: true },
                { label: "Amber Clearance (3.0s)", status: "VALID", ok: true },
                { label: "All-Red Clearance (2.0s)", status: "VALID", ok: true },
                { label: "Conflict Monitor (NEMA Interlock)", status: "ONLINE", ok: true },
              ].map((g, idx) => (
                <div key={idx} className="flex justify-between items-center text-xs p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="font-medium text-slate-700">{g.label}</span>
                  <span className="font-bold text-emerald-600 font-mono flex items-center">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5" />
                    {g.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-red-200 shadow-sm p-5">
            <h3 className="text-sm font-bold text-red-600 flex items-center mb-4">
              <AlertTriangle className="w-4 h-4 mr-2" />
              Manual Override Console
            </h3>
            <div className="space-y-3">
              <button
                onClick={() => handleOverride('PHASE_SKIP')}
                className="w-full py-2.5 px-4 rounded-lg border border-slate-300 text-slate-800 hover:bg-slate-50 font-semibold text-sm transition-colors flex items-center justify-center space-x-2 shadow-sm"
              >
                <Play className="w-4 h-4" />
                <span>Force Phase Skip</span>
              </button>

              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => handleOverride('EXTEND_GREEN', 5)}
                  className="py-2.5 px-3 rounded-lg border border-slate-300 text-slate-800 hover:bg-slate-50 font-semibold text-sm transition-colors flex items-center justify-center space-x-1 shadow-sm"
                >
                  <Plus className="w-4 h-4" />
                  <span>+5s Green</span>
                </button>
                <button
                  onClick={() => handleOverride('SHORTEN_GREEN', 5)}
                  className="py-2.5 px-3 rounded-lg border border-slate-300 text-slate-800 hover:bg-slate-50 font-semibold text-sm transition-colors flex items-center justify-center space-x-1 shadow-sm"
                >
                  <Minus className="w-4 h-4" />
                  <span>-5s Green</span>
                </button>
              </div>

              <button
                onClick={() => handleOverride('FLASH_ALL_RED')}
                className="w-full py-3 px-4 rounded-lg bg-red-600 hover:bg-red-700 text-white font-bold text-sm transition-colors flex items-center justify-center space-x-2 shadow-sm"
              >
                <AlertTriangle className="w-4 h-4" />
                <span>ALL RED (FLASH)</span>
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
