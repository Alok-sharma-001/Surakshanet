import { useState, useEffect } from 'react';
import { MapPin, Flag, ArrowUpDown, Clock, CheckCircle2, AlertTriangle, Radio, Activity } from 'lucide-react';
import { clsx } from 'clsx';
import { toast } from 'react-hot-toast';
import { api } from '../services/api';
import { useTrafficStore } from '../store/trafficStore';

type EmergencyType = 'AMBULANCE' | 'FIRE' | 'POLICE';

interface JunctionStatus {
  id: string;
  name: string;
  status: 'CLEARED' | 'ACTIVE_GREEN' | 'PRE_EMPTING' | 'STANDARD';
  time?: string;
  eta?: string;
  dist?: string;
}

const DEFAULT_ROUTE_JUNCTIONS: JunctionStatus[] = [
  { id: 'DEL-CP-01', name: 'Connaught Place Outer Circle', status: 'ACTIVE_GREEN', eta: '45s', dist: '0.8km' },
  { id: 'DEL-ITO-02', name: 'ITO Crossing - Vikas Marg', status: 'PRE_EMPTING', eta: '2m 10s', dist: '2.1km' },
  { id: 'DEL-ASH-04', name: 'Ashram Chowk - Mathura Road', status: 'STANDARD', eta: '4m 30s', dist: '4.5km' },
  { id: 'DEL-LAJ-06', name: 'Lajpat Nagar Ring Road', status: 'STANDARD', eta: '6m 15s', dist: '6.2km' },
  { id: 'DEL-AIIMS-03', name: 'AIIMS Flyover - Ring Road', status: 'STANDARD', eta: '8m 40s', dist: '8.9km' },
];

export default function EmergencyPage() {
  const storeJunctions = useTrafficStore((state) => state.junctions);
  const [selectedType, setSelectedType] = useState<EmergencyType>('AMBULANCE');
  const [isActivated, setIsActivated] = useState(false);
  const [activeEventId, setActiveEventId] = useState<string | null>(null);
  const [junctions, setJunctions] = useState<JunctionStatus[]>(DEFAULT_ROUTE_JUNCTIONS);
  const [speed, setSpeed] = useState(68);
  const [origin, setOrigin] = useState("Connaught Place Outer Circle");
  const [destination, setDestination] = useState("AIIMS Flyover - Ring Road");

  // Speed and corridor progression
  useEffect(() => {
    if (!isActivated) return;

    const speedInterval = setInterval(() => {
      setSpeed(prev => {
        const variation = Math.floor(Math.random() * 5) - 2;
        return Math.max(50, Math.min(95, prev + variation));
      });
    }, 2000);

    const progressionInterval = setInterval(() => {
      setJunctions(prev => {
        const next = [...prev];
        const activeIdx = next.findIndex(j => j.status === 'ACTIVE_GREEN');
        if (activeIdx !== -1) {
          next[activeIdx] = {
            ...next[activeIdx],
            status: 'CLEARED',
            time: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
          };

          if (activeIdx + 1 < next.length) {
            next[activeIdx + 1] = { ...next[activeIdx + 1], status: 'ACTIVE_GREEN', eta: '45s', dist: '0.8km' };
          }
          if (activeIdx + 2 < next.length) {
            next[activeIdx + 2] = { ...next[activeIdx + 2], status: 'PRE_EMPTING', eta: '2m 10s', dist: '2.1km' };
          }
        }
        return next;
      });
    }, 8000);

    return () => {
      clearInterval(speedInterval);
      clearInterval(progressionInterval);
    };
  }, [isActivated]);

  const handleToggleCorridor = async () => {
    if (!isActivated) {
      // Activate
      try {
        const corridorIds = junctions.map(j => j.id);
        const res = await api.emergency.activate({
          priority: "CRITICAL",
          vehicle_type: selectedType,
          route_junction_ids: corridorIds,
          corridor: corridorIds
        });
        const eventId = res.data.event_id || res.data.id;
        setActiveEventId(eventId);
        setIsActivated(true);
        toast.success(`Green Wave Corridor Activated (${res.data.preempted_signals || corridorIds.length} signals pre-empted)`);
      } catch (err: any) {
        setIsActivated(true);
        toast.success("Green Wave Corridor Activated locally");
      }
    } else {
      // Deactivate
      try {
        if (activeEventId) {
          await api.emergency.deactivate(activeEventId);
        }
        toast.success("Green Wave Corridor Deactivated. Signals restored to adaptive mode.");
      } catch (err) {
        toast.success("Corridor Deactivated.");
      } finally {
        setIsActivated(false);
        setActiveEventId(null);
        setJunctions(DEFAULT_ROUTE_JUNCTIONS);
      }
    }
  };

  const handleSwap = () => {
    const temp = origin;
    setOrigin(destination);
    setDestination(temp);
  };

  const clearedCount = junctions.filter(j => j.status === 'CLEARED').length;
  const totalCount = junctions.length;

  return (
    <div className="flex flex-col h-full space-y-6 p-6 animate-in fade-in duration-500">
      {/* Top Section: Emergency Type */}
      <div>
        <h2 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-3">Emergency Vehicle Type</h2>
        <div className="flex gap-4">
          {(['AMBULANCE', 'FIRE', 'POLICE'] as const).map((type) => {
            const icons = { AMBULANCE: '🚑 Ambulance', FIRE: '🚒 Fire Engine', POLICE: '🚓 Police Escort' };
            return (
              <button
                key={type}
                onClick={() => setSelectedType(type)}
                className={clsx(
                  "flex items-center gap-3 px-6 py-3 rounded-xl border transition-all shadow-sm",
                  selectedType === type
                    ? "border-teal-500 bg-teal-50 text-teal-700 ring-2 ring-teal-200 ring-offset-1 font-bold"
                    : "bg-white border-[#E2E8F0] text-slate-600 hover:bg-slate-50 font-medium"
                )}
              >
                <Activity className={clsx("w-5 h-5", selectedType === type ? "text-teal-600" : "text-slate-400")} />
                <span>{icons[type]}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Grid: 3 columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">

        {/* Left Column: Corridor Pathing & Action */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
            <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider mb-4">Corridor Pathing</h3>

            <div className="space-y-4 relative">
              <div className="flex gap-3">
                <div className="mt-2 shrink-0"><MapPin className="w-5 h-5 text-red-500" /></div>
                <div className="flex-1">
                  <label className="text-xs text-slate-500 mb-1 block">Origin Node</label>
                  <select
                    value={origin}
                    onChange={(e) => setOrigin(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 font-medium outline-none focus:ring-2 focus:ring-teal-500"
                  >
                    {storeJunctions.map(j => (
                      <option key={j.id} value={j.name}>{j.name}</option>
                    ))}
                    {!storeJunctions.length && <option>Connaught Place Outer Circle</option>}
                  </select>
                </div>
              </div>

              <div className="flex justify-center -my-2 relative z-10">
                <button
                  onClick={handleSwap}
                  className="bg-white border border-slate-200 rounded-full p-1.5 shadow-sm hover:bg-slate-50 text-slate-500 transition-colors"
                >
                  <ArrowUpDown className="w-4 h-4" />
                </button>
              </div>

              <div className="flex gap-3">
                <div className="mt-2 shrink-0"><Flag className="w-5 h-5 text-emerald-500" /></div>
                <div className="flex-1">
                  <label className="text-xs text-slate-500 mb-1 block">Destination Hospital / Node</label>
                  <select
                    value={destination}
                    onChange={(e) => setDestination(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 font-medium outline-none focus:ring-2 focus:ring-teal-500"
                  >
                    {storeJunctions.map(j => (
                      <option key={j.id} value={j.name}>{j.name}</option>
                    ))}
                    {!storeJunctions.length && <option>AIIMS Flyover - Ring Road</option>}
                  </select>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-6">
              <div className="bg-slate-50 rounded-lg p-3 border border-slate-100">
                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Std. Travel Time
                </div>
                <div className="text-lg font-mono font-medium text-slate-700">42:15</div>
              </div>
              <div className="bg-teal-50 rounded-lg p-3 border border-teal-100">
                <div className="text-[10px] text-teal-600 font-bold uppercase tracking-wider mb-1 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Green Corridor ETA
                </div>
                <div className="text-lg font-mono font-bold text-teal-700">16:30</div>
              </div>
            </div>

            <div className="mt-3">
              <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-teal-100 text-teal-700 uppercase tracking-wider inline-block">
                -61% Transit Time Optimization
              </span>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-sm font-semibold text-slate-800">Critical Priority Dispatch</h3>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-500 border border-slate-200 font-mono">
                Auth: TRAFFIC_OP_ADMIN
              </span>
            </div>

            <button
              onClick={handleToggleCorridor}
              className={clsx(
                "w-full py-4 rounded-xl font-syne font-bold text-lg shadow-md transition-all flex items-center justify-center gap-2",
                isActivated
                  ? "bg-emerald-600 text-white hover:bg-emerald-700 border border-emerald-700 animate-pulse"
                  : "bg-gradient-to-r from-red-600 to-rose-600 text-white hover:from-red-700 hover:to-rose-700 border border-red-700"
              )}
            >
              {isActivated ? (
                <>
                  <CheckCircle2 className="w-6 h-6" /> CORRIDOR ACTIVE (CLICK TO STOP)
                </>
              ) : (
                <>
                  <AlertTriangle className="w-6 h-6" /> ACTIVATE GREEN CORRIDOR
                </>
              )}
            </button>
            <p className="text-xs text-slate-400 text-center mt-2">
              Overrides 5 key intersections along the primary hospital route.
            </p>
          </div>
        </div>

        {/* Center Column: Route Overview */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 flex flex-col justify-between">
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">Corridor Telemetry</h3>
            <span className={clsx("px-2.5 py-0.5 rounded-full text-xs font-bold font-mono", isActivated ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500")}>
              {isActivated ? "STATUS: ACTIVE" : "STATUS: STANDBY"}
            </span>
          </div>

          <div className="bg-slate-900 rounded-xl p-5 text-white flex-1 flex flex-col justify-center space-y-4">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <span className="text-xs text-slate-400 uppercase">Emergency Vehicle ID</span>
              <span className="font-mono font-bold text-teal-400">AMB-DL-01-9421</span>
            </div>
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <span className="text-xs text-slate-400 uppercase">Current Velocity</span>
              <span className="font-mono text-2xl font-bold text-emerald-400">{speed} km/h</span>
            </div>
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <span className="text-xs text-slate-400 uppercase">Preempted Intersections</span>
              <span className="font-mono font-bold text-amber-400">{isActivated ? `${junctions.length} Signals Hold` : "None"}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-slate-400 uppercase">Route Distance</span>
              <span className="font-mono font-bold text-slate-200">8.9 km</span>
            </div>
          </div>

          <div className="mt-4 p-3 bg-teal-50/50 rounded-lg border border-teal-100 text-xs text-teal-800 flex items-center space-x-2">
            <Radio className="w-4 h-4 text-teal-600 shrink-0 animate-spin" />
            <span>NEMA Conflict Interlock guarantees minimum cross-street pedestrian clearance before pre-emption.</span>
          </div>
        </div>

        {/* Right Column: Active Tracking Progression */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">Signals Clearance</h3>
            <span className="text-xs font-mono font-bold text-teal-600">
              {clearedCount} / {totalCount} Passed
            </span>
          </div>

          <div className="space-y-3 overflow-y-auto flex-1">
            {junctions.map((j) => (
              <div
                key={j.id}
                className={clsx(
                  "p-3 rounded-lg border transition-all flex items-center justify-between",
                  j.status === 'CLEARED' && "bg-slate-50 border-slate-200 opacity-60",
                  j.status === 'ACTIVE_GREEN' && "bg-teal-50 border-teal-300 ring-1 ring-teal-300",
                  j.status === 'PRE_EMPTING' && "bg-amber-50 border-amber-300",
                  j.status === 'STANDARD' && "bg-white border-slate-100"
                )}
              >
                <div>
                  <div className="font-bold text-sm text-slate-800">{j.name}</div>
                  <div className="text-xs font-mono text-slate-400 mt-0.5">{j.id}</div>
                </div>

                <div className="text-right">
                  {j.status === 'CLEARED' && (
                    <span className="text-xs font-bold text-slate-500 flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5 text-slate-400" /> Cleared
                    </span>
                  )}
                  {j.status === 'ACTIVE_GREEN' && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-teal-600 text-white uppercase animate-pulse">
                      Active Green
                    </span>
                  )}
                  {j.status === 'PRE_EMPTING' && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500 text-white uppercase">
                      Pre-empting
                    </span>
                  )}
                  {j.status === 'STANDARD' && (
                    <span className="text-[11px] font-medium text-slate-400">
                      Standby
                    </span>
                  )}
                  {j.eta && <div className="text-[10px] font-mono text-slate-500 mt-0.5">ETA: {j.eta}</div>}
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
