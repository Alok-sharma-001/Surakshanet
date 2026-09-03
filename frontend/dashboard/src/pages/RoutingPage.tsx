import { useState } from 'react';
import { MapPin, Navigation, Search, Radio, Clock, Save, AlertTriangle } from 'lucide-react';
import clsx from 'clsx';

export default function RoutingPage() {
  const [origin, setOrigin] = useState("Sector 42, High Street");
  const [destination, setDestination] = useState("Industrial Hub North");
  const [isCalculating, setIsCalculating] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [selectedRoute, setSelectedRoute] = useState<string | null>("alpha");
  const [line1, setLine1] = useState("HEAVY TRAFFIC AHEAD");
  const [line2, setLine2] = useState("USE ALT ROUTE - BETA RING");

  const handleCalculate = () => {
    setIsCalculating(true);
    setShowResults(false);
    setTimeout(() => {
      setIsCalculating(false);
      setShowResults(true);
    }, 1200);
  };

  return (
    <div className="h-full flex flex-col gap-6 p-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-syne font-bold text-slate-900">Dynamic Routing & VMS</h1>
          <p className="text-sm text-slate-500">Route optimization and Variable Message Sign broadcast management</p>
        </div>
      </div>

      <div className="flex-1 flex gap-6 overflow-hidden min-h-0">
        {/* Left Column - Route Optimizer */}
        <div className="w-80 flex flex-col gap-4 overflow-y-auto pr-1">
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 flex flex-col gap-4">
            <h2 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">Route Optimizer</h2>
            
            <div className="flex flex-col gap-3 relative">
              <div className="absolute left-[11px] top-7 bottom-7 w-0.5 bg-slate-200"></div>
              
              <div className="flex items-center gap-3 relative z-10">
                <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
                  <div className="w-2.5 h-2.5 rounded-full bg-blue-600"></div>
                </div>
                <input 
                  type="text" 
                  value={origin}
                  onChange={(e) => setOrigin(e.target.value)}
                  className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>

              <div className="flex items-center gap-3 relative z-10">
                <div className="w-6 h-6 rounded-full bg-red-100 flex items-center justify-center shrink-0">
                  <MapPin className="w-3.5 h-3.5 text-red-600" />
                </div>
                <input 
                  type="text" 
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>
            </div>

            <button 
              onClick={handleCalculate}
              disabled={isCalculating}
              className="w-full flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-700 text-white py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-70"
            >
              {isCalculating ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  Calculating...
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  Calculate Paths
                </>
              )}
            </button>
          </div>

          {showResults && (
            <div className="flex flex-col gap-3 animate-in fade-in slide-in-from-bottom-4 duration-500">
              <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider pt-2">Results</h3>
              
              <div 
                onClick={() => setSelectedRoute('alpha')}
                className={clsx(
                  "bg-white rounded-xl border shadow-sm p-4 cursor-pointer transition-all hover:border-teal-300",
                  selectedRoute === 'alpha' ? "border-teal-500 ring-1 ring-teal-500" : "border-[#E2E8F0]"
                )}
              >
                <div className="flex justify-between items-start mb-2">
                  <div className="font-semibold text-slate-800">Alpha Line</div>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-600">Recommended</span>
                </div>
                <div className="flex items-end justify-between">
                  <div className="flex flex-col">
                    <span className="text-2xl font-mono text-emerald-500 font-bold">14m</span>
                    <span className="text-xs text-slate-500">ETA • 5.2 km</span>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className="text-sm font-mono text-teal-600">0.82</span>
                    <span className="text-[10px] text-slate-400 uppercase">Congestion Idx</span>
                  </div>
                </div>
              </div>

              <div 
                onClick={() => setSelectedRoute('beta')}
                className={clsx(
                  "bg-white rounded-xl border shadow-sm p-4 cursor-pointer transition-all hover:border-teal-300",
                  selectedRoute === 'beta' ? "border-teal-500 ring-1 ring-teal-500" : "border-[#E2E8F0]"
                )}
              >
                <div className="flex justify-between items-start mb-2">
                  <div className="font-semibold text-slate-800">Beta Ring</div>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-600">Alt Route</span>
                </div>
                <div className="flex items-end justify-between">
                  <div className="flex flex-col">
                    <span className="text-2xl font-mono text-amber-500 font-bold">22m</span>
                    <span className="text-xs text-slate-500">ETA • 6.8 km</span>
                  </div>
                  <div className="flex flex-col items-end">
                    <div className="flex items-center gap-1 text-red-500">
                      <AlertTriangle className="w-3 h-3" />
                      <span className="text-sm font-mono">1.45</span>
                    </div>
                    <span className="text-[10px] text-slate-400 uppercase">Congestion Idx</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Center Column - Map */}
        <div className="flex-1 bg-slate-100 rounded-xl border border-slate-200 overflow-hidden relative flex items-center justify-center">
          <div className="absolute inset-0 opacity-20 pointer-events-none" style={{
            backgroundImage: `radial-gradient(circle at 2px 2px, slate 1px, transparent 0)`,
            backgroundSize: '24px 24px'
          }}></div>
          <div className="flex flex-col items-center gap-2 text-slate-400 z-10">
            <Navigation className="w-8 h-8 opacity-50" />
            <span className="font-medium text-sm">Interactive Map View</span>
            {showResults && selectedRoute && (
              <span className="text-xs text-teal-600 font-medium px-3 py-1 bg-teal-50 rounded-full mt-2 border border-teal-100">
                Displaying {selectedRoute === 'alpha' ? 'Alpha Line' : 'Beta Ring'}
              </span>
            )}
          </div>
        </div>

        {/* Right Column - VMS Broadcaster */}
        <div className="w-96 flex flex-col gap-4 overflow-y-auto pr-1">
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 flex flex-col gap-4">
            <div className="flex justify-between items-center">
              <h2 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">VMS Broadcaster</h2>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-600 border border-amber-100 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>
                Live Edit Mode
              </span>
            </div>

            {/* LED Preview */}
            <div className="bg-[#1a1a1a] border-[4px] border-[#222222] rounded-xl p-4 shadow-[inset_0_0_20px_rgba(0,0,0,0.8)]">
              <div className="flex flex-col gap-2">
                <div className="h-6 flex items-center overflow-hidden">
                  <span className="text-amber-400 font-mono font-bold text-lg tracking-[0.15em] uppercase whitespace-nowrap" style={{ textShadow: '0 0 8px rgba(251, 191, 36, 0.6)' }}>
                    {line1 || '\u00A0'}
                  </span>
                </div>
                <div className="h-6 flex items-center overflow-hidden">
                  <span className="text-amber-400 font-mono font-bold text-lg tracking-[0.15em] uppercase whitespace-nowrap" style={{ textShadow: '0 0 8px rgba(251, 191, 36, 0.6)' }}>
                    {line2 || '\u00A0'}
                  </span>
                </div>
              </div>
              <div className="mt-3 flex justify-between items-center border-t border-[#333333] pt-2">
                <span className="text-[#666666] text-[10px] font-mono">PANEL DIMENSIONS: 24x4</span>
                <span className="text-[#666666] text-[10px] font-mono">STATUS: ONLINE</span>
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-slate-600">Target VMS Panels</label>
                <select className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 bg-white">
                  <option>Cluster A (North Corr.) [4 Panels]</option>
                  <option>Cluster B (South Corr.) [2 Panels]</option>
                  <option>Highway Gantry G-12 [1 Panel]</option>
                  <option>All Zones [Broadcast]</option>
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-slate-600 flex justify-between">
                  Message Line 1 <span className="text-slate-400">{line1.length}/24</span>
                </label>
                <input 
                  type="text" 
                  maxLength={24}
                  value={line1}
                  onChange={(e) => setLine1(e.target.value.toUpperCase())}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 font-mono uppercase"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-slate-600 flex justify-between">
                  Message Line 2 <span className="text-slate-400">{line2.length}/24</span>
                </label>
                <input 
                  type="text" 
                  maxLength={24}
                  value={line2}
                  onChange={(e) => setLine2(e.target.value.toUpperCase())}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 font-mono uppercase"
                />
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <button className="flex-1 flex items-center justify-center gap-2 border border-slate-200 hover:bg-slate-50 text-slate-700 py-2 rounded-lg text-sm font-medium transition-colors">
                <Save className="w-4 h-4" />
                Save Draft
              </button>
              <button className="flex-1 flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-700 text-white py-2 rounded-lg text-sm font-medium transition-colors">
                <Radio className="w-4 h-4" />
                Broadcast
              </button>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 flex flex-col gap-4">
            <div className="flex justify-between items-center">
              <h2 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">Active Broadcasts</h2>
              <Clock className="w-4 h-4 text-slate-400" />
            </div>

            <div className="flex flex-col gap-3">
              <div className="flex gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
                <div className="w-2 h-2 rounded-full bg-emerald-500 mt-1.5 shrink-0"></div>
                <div className="flex flex-col gap-1 min-w-0">
                  <div className="flex justify-between items-start">
                    <span className="text-xs font-medium text-slate-700">Cluster A</span>
                    <span className="text-[10px] text-slate-500 font-mono">08:42:15</span>
                  </div>
                  <p className="text-xs text-slate-600 font-mono truncate">HEAVY TRAFFIC AHEAD / USE ALT ROUTE</p>
                </div>
              </div>

              <div className="flex gap-3 p-3 rounded-lg border border-slate-100">
                <div className="w-2 h-2 rounded-full bg-slate-300 mt-1.5 shrink-0"></div>
                <div className="flex flex-col gap-1 min-w-0">
                  <div className="flex justify-between items-start">
                    <span className="text-xs font-medium text-slate-700">VMS-12</span>
                    <span className="text-[10px] text-slate-500 font-mono">07:15:00</span>
                  </div>
                  <p className="text-xs text-slate-600 font-mono truncate">ACCIDENT CLEARED / RESUME NORMAL SPEED</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
