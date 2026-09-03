import { useState, useEffect } from 'react';
import { Siren, MapPin, Flag, ArrowUpDown, Clock, CheckCircle2, AlertTriangle, Radio, Activity } from 'lucide-react';
import { clsx } from 'clsx';

type EmergencyType = 'AMBULANCE' | 'FIRE' | 'POLICE';

interface JunctionStatus {
  id: string;
  name: string;
  status: 'CLEARED' | 'ACTIVE_GREEN' | 'PRE_EMPTING' | 'STANDARD';
  time?: string;
  eta?: string;
  dist?: string;
}

const INITIAL_JUNCTIONS: JunctionStatus[] = [
  { id: 'JNC-01', name: 'Sarita Vihar Underpass', status: 'CLEARED', time: '14:02:11' },
  { id: 'JNC-02', name: 'Mathura Rd Crossing', status: 'CLEARED', time: '14:04:45' },
  { id: 'JNC-03', name: 'Ashram Chowk', status: 'ACTIVE_GREEN', eta: '45s', dist: '0.8km' },
  { id: 'JNC-04', name: 'Ring Road Merge', status: 'PRE_EMPTING', eta: '2m 10s', dist: '2.1km' },
  { id: 'JNC-05', name: 'Lajpat Nagar Flyover', status: 'STANDARD' },
  { id: 'JNC-06', name: 'Moolchand Underpass', status: 'STANDARD' },
  { id: 'JNC-07', name: 'Defence Colony', status: 'STANDARD' },
  { id: 'JNC-08', name: 'South Ex Pt 1', status: 'STANDARD' },
];

export default function EmergencyPage() {
  const [selectedType, setSelectedType] = useState<EmergencyType>('AMBULANCE');
  const [isActivated, setIsActivated] = useState(false);
  const [junctions, setJunctions] = useState<JunctionStatus[]>(INITIAL_JUNCTIONS);
  const [speed, setSpeed] = useState(68);

  useEffect(() => {
    if (!isActivated) return;
    
    // Simulate speed variations
    const speedInterval = setInterval(() => {
      setSpeed(prev => {
        const variation = Math.floor(Math.random() * 5) - 2;
        const newSpeed = prev + variation;
        return Math.max(40, Math.min(100, newSpeed));
      });
    }, 2000);

    // Simulate corridor clearing progression
    const progressionInterval = setInterval(() => {
      setJunctions(prev => {
        const next = [...prev];
        
        // Find active green
        const activeIdx = next.findIndex(j => j.status === 'ACTIVE_GREEN');
        if (activeIdx !== -1) {
          next[activeIdx] = { ...next[activeIdx], status: 'CLEARED', time: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) };
          
          if (activeIdx + 1 < next.length) {
            next[activeIdx + 1] = { ...next[activeIdx + 1], status: 'ACTIVE_GREEN', eta: '45s', dist: '0.8km' };
          }
          
          if (activeIdx + 2 < next.length) {
            next[activeIdx + 2] = { ...next[activeIdx + 2], status: 'PRE_EMPTING', eta: '2m 10s', dist: '2.1km' };
          }
        }
        
        return next;
      });
    }, 10000); // Progress every 10 seconds for demo purposes

    return () => {
      clearInterval(speedInterval);
      clearInterval(progressionInterval);
    };
  }, [isActivated]);

  const clearedCount = junctions.filter(j => j.status === 'CLEARED').length;
  const totalCount = junctions.length;

  return (
    <div className="flex flex-col h-full space-y-6">
      {/* Top Section: Emergency Type */}
      <div>
        <h2 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-3">Emergency Type</h2>
        <div className="flex gap-4">
          <button 
            onClick={() => setSelectedType('AMBULANCE')}
            className={clsx(
              "flex items-center gap-3 px-6 py-3 rounded-xl border transition-all shadow-sm",
              selectedType === 'AMBULANCE' 
                ? "border-teal-500 bg-teal-50 text-teal-700 ring-2 ring-teal-200 ring-offset-1" 
                : "bg-white border-[#E2E8F0] text-slate-600 hover:bg-slate-50"
            )}
          >
            <Activity className={clsx("w-5 h-5", selectedType === 'AMBULANCE' ? "text-teal-600" : "text-slate-400")} />
            <span className="font-semibold">Ambulance (🚑)</span>
          </button>
          
          <button 
            onClick={() => setSelectedType('FIRE')}
            className={clsx(
              "flex items-center gap-3 px-6 py-3 rounded-xl border transition-all shadow-sm",
              selectedType === 'FIRE' 
                ? "border-teal-500 bg-teal-50 text-teal-700 ring-2 ring-teal-200 ring-offset-1" 
                : "bg-white border-[#E2E8F0] text-slate-600 hover:bg-slate-50"
            )}
          >
            <AlertTriangle className={clsx("w-5 h-5", selectedType === 'FIRE' ? "text-teal-600" : "text-slate-400")} />
            <span className="font-semibold">Fire Engine (🚒)</span>
          </button>
          
          <button 
            onClick={() => setSelectedType('POLICE')}
            className={clsx(
              "flex items-center gap-3 px-6 py-3 rounded-xl border transition-all shadow-sm",
              selectedType === 'POLICE' 
                ? "border-teal-500 bg-teal-50 text-teal-700 ring-2 ring-teal-200 ring-offset-1" 
                : "bg-white border-[#E2E8F0] text-slate-600 hover:bg-slate-50"
            )}
          >
            <Siren className={clsx("w-5 h-5", selectedType === 'POLICE' ? "text-teal-600" : "text-slate-400")} />
            <span className="font-semibold">Police (🚓)</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 min-h-0">
        {/* Left Column */}
        <div className="lg:col-span-3 flex flex-col gap-6">
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 flex-1">
            <h3 className="text-sm font-semibold text-slate-800 mb-5">Corridor Pathing</h3>
            
            <div className="space-y-4 relative">
              <div className="flex gap-3">
                <div className="mt-2 shrink-0"><MapPin className="w-5 h-5 text-red-500" /></div>
                <div className="flex-1">
                  <label className="text-xs text-slate-500 mb-1 block">Origin</label>
                  <input type="text" value="Apollo Hospital, Sarita Vihar" readOnly className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 font-medium outline-none" />
                </div>
              </div>
              
              <div className="absolute left-3 top-[3.25rem] bottom-[4rem] w-0.5 bg-slate-200 border-dashed border-l-2 border-slate-200 -z-0"></div>
              
              <div className="flex justify-center -my-2 relative z-10">
                <button className="bg-white border border-slate-200 rounded-full p-1.5 shadow-sm hover:bg-slate-50 text-slate-500 transition-colors">
                  <ArrowUpDown className="w-4 h-4" />
                </button>
              </div>

              <div className="flex gap-3">
                <div className="mt-2 shrink-0"><Flag className="w-5 h-5 text-emerald-500" /></div>
                <div className="flex-1">
                  <label className="text-xs text-slate-500 mb-1 block">Destination</label>
                  <input type="text" value="Medanta Institute, Gurugram" readOnly className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 font-medium outline-none" />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-8">
              <div className="bg-slate-50 rounded-lg p-3 border border-slate-100">
                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1 flex items-center gap-1"><Clock className="w-3 h-3" /> Std. Time</div>
                <div className="text-lg font-mono font-medium text-slate-700">45:20</div>
              </div>
              <div className="bg-teal-50 rounded-lg p-3 border border-teal-100">
                <div className="text-[10px] text-teal-600 font-bold uppercase tracking-wider mb-1 flex items-center gap-1"><Clock className="w-3 h-3" /> Est. Time</div>
                <div className="flex items-end gap-2">
                  <div className="text-lg font-mono font-bold text-teal-700">18:45</div>
                </div>
              </div>
            </div>
            
            <div className="mt-3">
               <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-teal-100 text-teal-700 uppercase tracking-wider inline-block">
                -58% Transit Time
              </span>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
             <div className="flex justify-between items-center mb-4">
              <h3 className="text-sm font-semibold text-slate-800">Critical Action</h3>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-500 border border-slate-200 font-mono">Auth: ADMIN_01</span>
             </div>
             
             <button 
              onClick={() => setIsActivated(!isActivated)}
              className={clsx(
                "w-full py-4 rounded-xl font-syne font-bold text-lg shadow-md transition-all flex items-center justify-center gap-2",
                isActivated 
                  ? "bg-emerald-500 text-white hover:bg-emerald-600 border border-emerald-600" 
                  : "bg-gradient-to-r from-red-500 to-rose-600 text-white hover:from-red-600 hover:to-rose-700 border border-red-700"
              )}
             >
                {isActivated ? (
                  <>
                    <CheckCircle2 className="w-6 h-6" /> CORRIDOR ACTIVE
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-6 h-6" /> ACTIVATE GREEN CORRIDOR
                  </>
                )}
             </button>
             <p className="text-xs text-slate-500 text-center mt-3">
               Overrides {totalCount} signals along standard operational path.
             </p>
          </div>
        </div>

        {/* Center Column: Map */}
        <div className="lg:col-span-5 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-1.5 flex flex-col relative overflow-hidden">
          <div className="absolute top-4 left-4 z-10 bg-white/90 backdrop-blur px-3 py-1.5 rounded-lg shadow-sm border border-slate-200 flex items-center gap-2">
            <Radio className="w-4 h-4 text-teal-600 animate-pulse" />
            <span className="text-xs font-semibold text-slate-700">Live Telemetry</span>
          </div>
          <div className="w-full h-full bg-slate-100 rounded-lg flex items-center justify-center overflow-hidden relative">
            <div className="text-slate-400 font-medium flex flex-col items-center gap-2">
              <MapPin className="w-8 h-8 opacity-50" />
              <span>Map View - Corridor Visualization</span>
            </div>
            
            {/* Fake route SVG */}
            <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
              <path d="M 20 80 Q 40 70 50 50 T 80 20" fill="none" stroke={isActivated ? "#0d9488" : "#cbd5e1"} strokeWidth="2" strokeDasharray={isActivated ? "4 2" : "none"} className={clsx(isActivated && "animate-[dash_1s_linear_infinite]")} />
              
              {isActivated && (
                <circle cx="50" cy="50" r="2" fill="#0d9488" className="animate-ping" />
              )}
            </svg>
            
            <style>{`
              @keyframes dash {
                to {
                  stroke-dashoffset: -6;
                }
              }
            `}</style>
          </div>
        </div>

        {/* Right Column: Tracking */}
        <div className="lg:col-span-4 bg-white rounded-xl border border-[#E2E8F0] shadow-sm flex flex-col overflow-hidden">
          <div className="p-5 border-b border-[#E2E8F0] bg-slate-50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.6)]"></div>
              <h3 className="text-sm font-bold text-slate-800">Active Tracking</h3>
            </div>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-200 text-slate-700 font-mono">VEH-ID: AMB-992A</span>
          </div>

          <div className="p-5 flex gap-6 items-center border-b border-[#E2E8F0]">
            <div className="relative w-24 h-24 shrink-0 flex items-center justify-center">
              <svg className="absolute inset-0 w-full h-full transform -rotate-90">
                <circle cx="48" cy="48" r="42" fill="none" stroke="#f1f5f9" strokeWidth="8" />
                <circle 
                  cx="48" 
                  cy="48" 
                  r="42" 
                  fill="none" 
                  stroke={isActivated ? "#0d9488" : "#94a3b8"} 
                  strokeWidth="8" 
                  strokeDasharray="264" 
                  strokeDashoffset={264 - (264 * (speed / 120))} 
                  className="transition-all duration-500 ease-in-out"
                />
              </svg>
              <div className="flex flex-col items-center">
                <span className="text-3xl font-syne font-bold text-slate-800 leading-none">{speed}</span>
                <span className="text-[10px] text-slate-500 font-bold uppercase">km/h</span>
              </div>
            </div>
            
            <div className="flex-1 space-y-3">
               <div>
                 <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-0.5">Destination</div>
                 <div className="text-sm font-semibold text-slate-800 truncate">Medanta Inst.</div>
               </div>
               <div>
                 <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-0.5">Corridor Progress</div>
                 <div className="text-sm font-semibold text-slate-800 font-mono">{clearedCount} / {totalCount} Cleared</div>
               </div>
            </div>
          </div>

          <div className="p-5 flex-1 overflow-y-auto">
            <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-4">Corridor Junctions</h4>
            <div className="space-y-4">
              {junctions.map((j, idx) => (
                <div key={j.id} className="relative pl-6">
                  {/* Timeline line */}
                  {idx < junctions.length - 1 && (
                    <div className={clsx(
                      "absolute left-2 top-4 bottom-[-16px] w-[2px]",
                      j.status === 'CLEARED' ? "bg-teal-500" : "bg-slate-200"
                    )}></div>
                  )}
                  
                  {/* Timeline node */}
                  <div className={clsx(
                    "absolute left-[3px] top-1 w-2.5 h-2.5 rounded-full border-2",
                    j.status === 'CLEARED' ? "bg-teal-500 border-teal-500" :
                    j.status === 'ACTIVE_GREEN' ? "bg-white border-teal-500 ring-4 ring-teal-50" :
                    j.status === 'PRE_EMPTING' ? "bg-white border-amber-500" :
                    "bg-white border-slate-300"
                  )}></div>
                  
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="text-xs font-mono text-slate-400 mb-0.5">{j.id}</div>
                      <div className="text-sm font-semibold text-slate-800">{j.name}</div>
                      
                      {j.status === 'CLEARED' && (
                        <div className="text-xs text-slate-500 flex items-center gap-1 mt-1">
                          <CheckCircle2 className="w-3.5 h-3.5 text-teal-500" />
                          Cleared at {j.time}
                        </div>
                      )}
                      
                      {j.status === 'ACTIVE_GREEN' && (
                        <div className="flex gap-2 mt-2">
                          <span className="px-2 py-0.5 bg-teal-50 text-teal-600 rounded text-[10px] font-bold uppercase border border-teal-100">Active Green</span>
                          {j.eta && <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px] font-mono border border-slate-200">ETA: {j.eta}</span>}
                          {j.dist && <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px] font-mono border border-slate-200">DIST: {j.dist}</span>}
                        </div>
                      )}
                      
                      {j.status === 'PRE_EMPTING' && (
                         <div className="flex gap-2 mt-2">
                          <span className="px-2 py-0.5 bg-amber-50 text-amber-600 rounded text-[10px] font-bold uppercase border border-amber-100">Pre-empting</span>
                          {j.eta && <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px] font-mono border border-slate-200">ETA: {j.eta}</span>}
                          {j.dist && <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px] font-mono border border-slate-200">DIST: {j.dist}</span>}
                        </div>
                      )}
                      
                      {j.status === 'STANDARD' && (
                        <div className="mt-1">
                           <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Standard Cycle</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
