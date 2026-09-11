import { useState, useEffect } from 'react';
import {
  MapPin,
  Flag,
  ArrowUpDown,
  CheckCircle2,
  AlertTriangle,
  Radio,
  Activity,
  Clock,
  ShieldCheck,
  TrendingDown,
  Navigation
} from 'lucide-react';
import { clsx } from 'clsx';
import { toast } from 'react-hot-toast';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine
} from 'recharts';
import { api } from '../services/api';
import { wsService } from '../services/websocket';
import { TelemetrySourceBadge } from '../components/TelemetrySourceBadge';

type EmergencyType = 'AMBULANCE' | 'FIRE' | 'POLICE';

interface JunctionCorridorState {
  junction_id: string;
  state: 'scheduled' | 'preempted' | 'passed' | 'restored' | string;
  eta_s?: number;
  activates_in_s?: number;
  activated_at?: string;
  passed_at?: string;
  restored_at?: string;
}

interface CorridorStatusResponse {
  event_id: string;
  status: string;
  vehicle_id?: string;
  current_position?: {
    link_id: string;
    progress: number;
    current_junction?: string;
  };
  next_junction?: string;
  next_junction_eta_s?: number;
  clearance_time_s?: number;
  junctions: JunctionCorridorState[];
  cross_street?: {
    max_red_s: number;
    threshold_s: number;
    compensating_phase_inserted: boolean;
  };
  source?: string;
}

interface RecoveryData {
  event_id: string;
  recovery_s: number | null;
  resolved: boolean;
  baseline_available: boolean;
  cross_street_baseline_delay_s: number | null;
  cross_street_peak_delay_s: number | null;
  series: Array<{ t: number; delay_s: number }>;
  source?: string;
}

export default function EmergencyPage() {
  const [selectedType, setSelectedType] = useState<EmergencyType>('AMBULANCE');
  const [isActivated, setIsActivated] = useState(false);
  const [activeEventId, setActiveEventId] = useState<string | null>(null);
  const [vehicleId, setVehicleId] = useState<string>('AMB-07');
  const [origin, setOrigin] = useState('West Expressway Entry');
  const [destination, setDestination] = useState('District Hospital');

  const [corridorData, setCorridorData] = useState<CorridorStatusResponse | null>(null);
  const [recoveryData, setRecoveryData] = useState<RecoveryData | null>(null);

  // Poll corridor state every 2s while active (SN-043 rolling activation)
  useEffect(() => {
    if (!activeEventId || !isActivated) return;

    const fetchCorridorState = async () => {
      try {
        const res = await api.emergency.getCorridor(activeEventId);
        if (res.data) {
          setCorridorData(res.data);
          if (res.data.status === 'COMPLETED') {
            setIsActivated(false);
            toast.success('Corridor pass-through completed! Measuring recovery.');
            fetchRecovery(activeEventId);
          }
        }
      } catch (err) {
        // May be closing
      }
    };

    fetchCorridorState();
    const interval = setInterval(fetchCorridorState, 2000);
    return () => clearInterval(interval);
  }, [activeEventId, isActivated]);

  // Check initial active emergency on mount
  useEffect(() => {
    api.emergency.getStatus().then((res: any) => {
      const active = res.data?.active_events;
      if (Array.isArray(active) && active.length > 0) {
        const ev = active[0];
        setIsActivated(true);
        setActiveEventId(ev.id);
        if (ev.vehicle_id) setVehicleId(ev.vehicle_id);
      }
    }).catch(() => {});

    wsService.connect('emergency');
    const unsub = wsService.onMessage('emergency', (data: any) => {
      if (data && data.type === 'EMERGENCY_ACTIVATED') {
        setIsActivated(true);
        if (data.event_id) setActiveEventId(data.event_id);
        if (data.vehicle_id) setVehicleId(data.vehicle_id);
      } else if (data && data.type === 'EMERGENCY_DEACTIVATED') {
        setIsActivated(false);
        if (data.event_id) {
          fetchRecovery(data.event_id);
        }
      }
    });

    return unsub;
  }, []);

  const fetchRecovery = async (eventId: string) => {
    try {
      const res = await api.emergency.getRecovery(eventId);
      if (res.data && res.data.recovery_s !== undefined) {
        setRecoveryData(res.data);
      }
    } catch (err: any) {
      if (err.response?.status === 503) {
        // Active corridor: recovery delay is unavailable while active (SN-048)
        setRecoveryData(null);
      }
    }
  };

  const handleToggleCorridor = async () => {
    if (!isActivated) {
      const corridorIds = ['J0', 'J1', 'J2', 'J3'];
      try {
        const res = await api.emergency.activate({
          priority: 'CRITICAL',
          vehicle_type: selectedType,
          vehicle_id: vehicleId,
          corridor: corridorIds,
          destination: {
            lat: 12.9177,
            lon: 77.6346,
            name: destination
          },
          origin: {
            lat: 12.9177,
            lon: 77.6211,
            name: origin
          }
        });

        const newId = res.data.event_id || res.data.id;
        setActiveEventId(newId);
        setIsActivated(true);
        setRecoveryData(null);
        toast.success('Rolling Green Wave Activated! Preemption scheduled in ETA order.');
      } catch (err: any) {
        toast.error('Failed to activate corridor. Check backend connectivity.');
      }
    } else {
      if (!activeEventId) return;
      try {
        await api.emergency.deactivate(activeEventId);
        setIsActivated(false);
        toast.success('Corridor Deactivated. Measuring cross-street recovery.');
        await fetchRecovery(activeEventId);
      } catch (err) {
        toast.error('Could not deactivate corridor. Signals may still be held.');
      }
    }
  };

  const handleSwap = () => {
    const temp = origin;
    setOrigin(destination);
    setDestination(temp);
  };

  return (
    <div className="flex flex-col h-full space-y-6 p-6 animate-in fade-in duration-500 overflow-y-auto">
      {/* Top Section: Vehicle & Priority Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Emergency Vehicle Class</h2>
          <div className="flex gap-3">
            {(['AMBULANCE', 'FIRE', 'POLICE'] as const).map((type) => {
              const icons = { AMBULANCE: '🚑 Ambulance', FIRE: '🚒 Fire Engine', POLICE: '🚓 Police Escort' };
              return (
                <button
                  key={type}
                  onClick={() => setSelectedType(type)}
                  className={clsx(
                    "flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-all",
                    selectedType === type
                      ? "border-emerald-500 bg-emerald-50 text-emerald-800 font-bold ring-1 ring-emerald-300"
                      : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50 font-medium"
                  )}
                >
                  <Activity className={clsx("w-4 h-4", selectedType === type ? "text-emerald-600" : "text-slate-400")} />
                  <span>{icons[type]}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className="text-[11px] font-mono text-slate-400 block">VEHICLE DISPATCH ID</span>
            <input
              type="text"
              value={vehicleId}
              onChange={(e) => setVehicleId(e.target.value.toUpperCase())}
              disabled={isActivated}
              className="w-28 text-sm font-mono font-bold text-slate-800 bg-slate-50 border border-slate-200 rounded px-2 py-1 outline-none text-right"
            />
          </div>
          <span className="px-3 py-1.5 rounded-lg text-xs font-bold font-mono bg-red-100 text-red-700 border border-red-200">
            CRITICAL PRIORITY
          </span>
        </div>
      </div>

      {/* Main Grid: 3 columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left Column: Corridor Controls & Dispatch */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">Route Configuration</h3>
              <TelemetrySourceBadge source={corridorData?.source || (isActivated ? 'sumo' : null)} />
            </div>

            <div className="space-y-3 relative">
              <div className="flex gap-3">
                <div className="mt-2 shrink-0"><MapPin className="w-5 h-5 text-red-500" /></div>
                <div className="flex-1">
                  <label className="text-xs text-slate-500 mb-1 block">Origin Access Point</label>
                  <input
                    type="text"
                    value={origin}
                    onChange={(e) => setOrigin(e.target.value)}
                    disabled={isActivated}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 font-medium"
                  />
                </div>
              </div>

              <div className="flex justify-center -my-2 relative z-10">
                <button
                  onClick={handleSwap}
                  disabled={isActivated}
                  className="bg-white border border-slate-200 rounded-full p-1.5 shadow-sm hover:bg-slate-50 text-slate-500 transition-colors"
                >
                  <ArrowUpDown className="w-4 h-4" />
                </button>
              </div>

              <div className="flex gap-3">
                <div className="mt-2 shrink-0"><Flag className="w-5 h-5 text-emerald-500" /></div>
                <div className="flex-1">
                  <label className="text-xs text-slate-500 mb-1 block">Hospital Destination</label>
                  <input
                    type="text"
                    value={destination}
                    onChange={(e) => setDestination(e.target.value)}
                    disabled={isActivated}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 font-medium"
                  />
                </div>
              </div>
            </div>

            <div className="mt-4 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600 flex items-center gap-2">
              <Navigation className="w-4 h-4 text-slate-500 shrink-0" />
              <span>A* Routing Profile: 0.7·travel_time + 0.3·distance (congestion penalty bypassed)</span>
            </div>
          </div>

          {/* Action Trigger Card */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <button
              onClick={handleToggleCorridor}
              className={clsx(
                "w-full py-4 rounded-xl font-bold text-base shadow-md transition-all flex items-center justify-center gap-2",
                isActivated
                  ? "bg-rose-600 text-white hover:bg-rose-700 border border-rose-700 animate-pulse"
                  : "bg-gradient-to-r from-emerald-600 to-teal-600 text-white hover:from-emerald-700 hover:to-teal-700 border border-emerald-700"
              )}
            >
              {isActivated ? (
                <>
                  <CheckCircle2 className="w-5 h-5" /> STOP GREEN CORRIDOR
                </>
              ) : (
                <>
                  <AlertTriangle className="w-5 h-5" /> ACTIVATE ROLLING GREEN WAVE
                </>
              )}
            </button>
            <p className="text-xs text-slate-400 text-center mt-2">
              Pre-emption propagates in ETA order. Signals revert immediately upon vehicle passage.
            </p>
          </div>

          {/* Starvation Guard Card */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-indigo-600" />
                Cross-Street Starvation Guard
              </h3>
              <span className="text-xs font-mono font-bold text-slate-500">SN-046</span>
            </div>

            <div className="space-y-3">
              <div className="flex justify-between text-xs">
                <span className="text-slate-500">Max Conflicting Red Time:</span>
                <span className="font-mono font-bold text-slate-800">
                  {corridorData?.cross_street?.max_red_s ?? 0}s / {corridorData?.cross_street?.threshold_s ?? 90}s
                </span>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div
                  className={clsx(
                    "h-full transition-all duration-500",
                    (corridorData?.cross_street?.max_red_s ?? 0) > 75
                      ? "bg-amber-500"
                      : "bg-indigo-500"
                  )}
                  style={{
                    width: `${Math.min(100, (((corridorData?.cross_street?.max_red_s ?? 0) / (corridorData?.cross_street?.threshold_s ?? 90)) * 100))}%`
                  }}
                />
              </div>

              {corridorData?.cross_street?.compensating_phase_inserted && (
                <div className="p-2 rounded bg-amber-50 border border-amber-200 text-[11px] text-amber-800 font-medium">
                  ✓ Compensating phase inserted behind vehicle on passed junctions.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Center Column: Propagating Wave Live Telemetry */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">Propagating Corridor</h3>
              <span className={clsx("px-2.5 py-0.5 rounded-full text-xs font-bold font-mono", isActivated ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500")}>
                {isActivated ? "STATUS: ACTIVE" : "STATUS: STANDBY"}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Target Next Node</span>
                <span className="text-lg font-bold font-mono text-slate-800">
                  {corridorData?.next_junction ?? 'J0'}
                </span>
                <span className="text-xs text-slate-500 block mt-0.5">
                  ETA: {corridorData?.next_junction_eta_s ?? '--'}s
                </span>
              </div>

              <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Estimated Clearance</span>
                <span className="text-lg font-bold font-mono text-emerald-700 flex items-center gap-1">
                  <Clock className="w-4 h-4" />
                  {corridorData?.clearance_time_s ? `${corridorData.clearance_time_s}s` : '--'}
                </span>
                <span className="text-xs text-slate-500 block mt-0.5">Countdown to clear corridor</span>
              </div>
            </div>

            {/* Visual Propagating Wave Strip */}
            <div className="p-4 bg-slate-900 rounded-xl text-white">
              <div className="flex justify-between items-center text-xs text-slate-400 mb-3">
                <span>West Entry (W)</span>
                <span className="font-mono text-emerald-400">Travelling Wave</span>
                <span>East Exit (E)</span>
              </div>

              <div className="flex items-center justify-between gap-2 relative">
                {(corridorData?.junctions ?? [
                  { junction_id: 'J0', state: 'scheduled' },
                  { junction_id: 'J1', state: 'scheduled' },
                  { junction_id: 'J2', state: 'scheduled' },
                  { junction_id: 'J3', state: 'scheduled' },
                ]).map((j) => {
                  const stateColors: Record<string, string> = {
                    preempted: 'bg-emerald-500 text-white ring-4 ring-emerald-400/30 animate-pulse',
                    passed: 'bg-amber-500 text-slate-900',
                    restored: 'bg-slate-700 text-slate-300',
                    scheduled: 'bg-slate-800 text-slate-400 border border-slate-700',
                  };

                  return (
                    <div key={j.junction_id} className="flex-1 flex flex-col items-center">
                      <div className={clsx("w-10 h-10 rounded-full flex items-center justify-center font-bold text-xs transition-all", stateColors[j.state] || stateColors.scheduled)}>
                        {j.junction_id}
                      </div>
                      <span className="text-[10px] font-mono text-slate-400 mt-1 uppercase">
                        {j.state}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Cross-Traffic Recovery Chart (SN-048) */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <div className="flex justify-between items-center mb-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-1.5">
                  <TrendingDown className="w-4 h-4 text-emerald-600" />
                  Post-Close Recovery Curve
                </h3>
                <span className="text-[11px] text-slate-400">Cross-street delay return to baseline, measured from real samples (SN-048)</span>
              </div>
              <TelemetrySourceBadge source={recoveryData?.source || (recoveryData ? 'sumo' : null)} />
            </div>

            {isActivated && (
              <div className="p-6 text-center bg-slate-50 rounded-lg border border-slate-200">
                <Clock className="w-6 h-6 text-slate-400 mx-auto mb-2" />
                <p className="text-xs text-slate-600 font-medium">Corridor currently ACTIVE.</p>
                <p className="text-[11px] text-slate-400 mt-1">
                  Recovery measurements (503 while active) will record and plot automatically when the corridor closes.
                </p>
              </div>
            )}

            {!isActivated && recoveryData && !recoveryData.baseline_available && (
              <div className="p-6 text-center text-xs text-slate-400 italic">
                No pre-activation baseline was available for this corridor — recovery cannot be assessed.
              </div>
            )}

            {!isActivated && recoveryData && recoveryData.baseline_available && recoveryData.series.length === 0 && (
              <div className="p-6 text-center bg-slate-50 rounded-lg border border-slate-200">
                <Clock className="w-6 h-6 text-slate-400 mx-auto mb-2" />
                <p className="text-xs text-slate-600 font-medium">Awaiting first post-close telemetry sample…</p>
              </div>
            )}

            {!isActivated && recoveryData && recoveryData.baseline_available && recoveryData.series.length > 0 && (
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="bg-slate-50 p-2 rounded">
                    <span className="text-[10px] text-slate-400 block">Baseline Delay</span>
                    <span className="font-bold text-slate-700">{recoveryData.cross_street_baseline_delay_s}s</span>
                  </div>
                  <div className="bg-red-50 p-2 rounded">
                    <span className="text-[10px] text-red-500 block">Peak Red Delay</span>
                    <span className="font-bold text-red-700">{recoveryData.cross_street_peak_delay_s}s</span>
                  </div>
                  <div className="bg-emerald-50 p-2 rounded">
                    <span className="text-[10px] text-emerald-600 block">Measured Recovery</span>
                    {recoveryData.resolved && recoveryData.recovery_s !== null ? (
                      <span className="font-bold text-emerald-700">{recoveryData.recovery_s}s ({(recoveryData.recovery_s / 60).toFixed(1)}m)</span>
                    ) : (
                      <span className="font-bold text-slate-400">still recovering…</span>
                    )}
                  </div>
                </div>

                <div className="h-44 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={recoveryData.series}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                      <XAxis dataKey="t" unit="s" tick={{ fontSize: 10 }} />
                      <YAxis unit="s" tick={{ fontSize: 10 }} domain={['dataMin - 5', 'dataMax + 5']} />
                      <Tooltip formatter={(val: any) => [`${val}s`, 'Cross-street Delay']} />
                      <ReferenceLine y={recoveryData.cross_street_baseline_delay_s ?? 0} stroke="#10B981" strokeDasharray="4 4" label="Baseline" />
                      <Line type="monotone" dataKey="delay_s" stroke="#0284C7" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {!isActivated && !recoveryData && (
              <div className="p-6 text-center text-xs text-slate-400 italic">
                Activate and complete a corridor run to measure and visualize post-corridor recovery delay.
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Junction Breakdown Table */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">Per-Junction Status</h3>
            <span className="text-xs font-mono font-bold text-emerald-600">
              {corridorData?.junctions?.length ?? 4} Nodes
            </span>
          </div>

          <div className="space-y-3 overflow-y-auto flex-1">
            {(corridorData?.junctions ?? [
              { junction_id: 'J0', state: 'scheduled', eta_s: 24 },
              { junction_id: 'J1', state: 'scheduled', eta_s: 61 },
              { junction_id: 'J2', state: 'scheduled', eta_s: 98 },
              { junction_id: 'J3', state: 'scheduled', eta_s: 140 },
            ]).map((j) => {
              const stateBadge: Record<string, { bg: string; text: string; label: string }> = {
                scheduled: { bg: 'bg-slate-100', text: 'text-slate-600', label: 'Scheduled' },
                preempted: { bg: 'bg-emerald-100', text: 'text-emerald-800', label: 'Pre-empted (Green)' },
                passed: { bg: 'bg-amber-100', text: 'text-amber-800', label: 'Vehicle Passed' },
                restored: { bg: 'bg-slate-200', text: 'text-slate-700', label: 'Program Restored' },
              };
              const badge = stateBadge[j.state] || stateBadge.scheduled;

              return (
                <div
                  key={j.junction_id}
                  className={clsx(
                    "p-3 rounded-lg border transition-all",
                    j.state === 'preempted'
                      ? "bg-emerald-50/50 border-emerald-300 shadow-sm"
                      : "bg-white border-slate-200"
                  )}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="font-bold text-sm text-slate-800">{j.junction_id}</span>
                      <span className="text-xs text-slate-400 block font-mono">
                        ETA: {j.eta_s ?? '--'}s
                      </span>
                    </div>

                    <span className={clsx("px-2 py-0.5 rounded text-[10px] font-bold uppercase", badge.bg, badge.text)}>
                      {badge.label}
                    </span>
                  </div>

                  {j.activates_in_s !== undefined && j.state === 'scheduled' && (
                    <div className="mt-2 text-[11px] text-slate-500 font-mono">
                      Clearance lead trigger in {j.activates_in_s}s
                    </div>
                  )}
                  {j.passed_at && (
                    <div className="mt-1 text-[10px] text-slate-400 font-mono">
                      Passed at t={j.passed_at}s · Program Verified
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="mt-4 p-3 bg-teal-50/50 rounded-lg border border-teal-100 text-xs text-teal-800 flex items-center gap-2">
            <Radio className="w-4 h-4 text-teal-600 shrink-0 animate-pulse" />
            <span>Real TraCI program logic captured prior to preemption and verified upon passage.</span>
          </div>
        </div>

      </div>
    </div>
  );
}
