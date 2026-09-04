import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Cpu, RefreshCw, AlertTriangle, ArrowDown, ArrowLeft, ArrowUp, ArrowRight, Video, ChevronLeft } from 'lucide-react';
import { clsx } from 'clsx';
import { toast } from 'react-hot-toast';
import { api } from '../services/api';
import { useTrafficStore } from '../store/trafficStore';

type ApproachDirection = 'NORTH' | 'EAST' | 'SOUTH' | 'WEST';

interface ApproachData {
  direction: ApproachDirection;
  label: string;
  icon: React.ElementType;
  status: 'NORMAL' | 'FLOWING' | 'CONGESTED' | 'HIGH_VOL';
  pcu: number;
  breakdown: { type: string; percent: number; color: string }[];
  queueLength: number;
  speed: number;
}

const DEFAULT_APPROACHES: ApproachData[] = [
  {
    direction: 'NORTH',
    label: 'North Bound (Vikas Marg)',
    icon: ArrowDown,
    status: 'HIGH_VOL',
    pcu: 342,
    breakdown: [
      { type: 'CAR', percent: 60, color: 'bg-blue-500' },
      { type: '2W', percent: 30, color: 'bg-orange-400' },
      { type: 'BUS', percent: 10, color: 'bg-purple-500' },
    ],
    queueLength: 45,
    speed: 22,
  },
  {
    direction: 'EAST',
    label: 'East Bound (Inner Circle)',
    icon: ArrowLeft,
    status: 'FLOWING',
    pcu: 184,
    breakdown: [
      { type: 'CAR', percent: 45, color: 'bg-blue-500' },
      { type: '2W', percent: 45, color: 'bg-orange-400' },
      { type: 'BUS', percent: 10, color: 'bg-purple-500' },
    ],
    queueLength: 12,
    speed: 38,
  },
  {
    direction: 'SOUTH',
    label: 'South Bound (Mathura Rd)',
    icon: ArrowUp,
    status: 'NORMAL',
    pcu: 245,
    breakdown: [
      { type: 'CAR', percent: 55, color: 'bg-blue-500' },
      { type: '2W', percent: 40, color: 'bg-orange-400' },
      { type: 'BUS', percent: 5, color: 'bg-purple-500' },
    ],
    queueLength: 28,
    speed: 28,
  },
  {
    direction: 'WEST',
    label: 'West Bound (Ring Road)',
    icon: ArrowRight,
    status: 'CONGESTED',
    pcu: 412,
    breakdown: [
      { type: 'CAR', percent: 70, color: 'bg-blue-500' },
      { type: '2W', percent: 20, color: 'bg-orange-400' },
      { type: 'BUS', percent: 10, color: 'bg-purple-500' },
    ],
    queueLength: 85,
    speed: 12,
  },
];

export default function JunctionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const storeJunctions = useTrafficStore((state) => state.junctions);
  const [countdown, setCountdown] = useState(14);
  const [junctionData, setJunctionData] = useState<any>(null);
  const [signalPlan, setSignalPlan] = useState<any>(null);
  const [approaches] = useState<ApproachData[]>(DEFAULT_APPROACHES);

  useEffect(() => {
    // Resolve junction metadata from store or API
    const junc = storeJunctions.find(j => j.id === id);
    if (junc) {
      setJunctionData(junc);
    } else if (id) {
      api.junctions.getById(id)
        .then(res => setJunctionData(res.data))
        .catch(() => setJunctionData({ id, name: "Smart Intersection Node" }));
    }

    // Fetch signal plan if available
    if (id) {
      api.signals.getByJunction(id)
        .then(res => setSignalPlan(res.data))
        .catch(() => {});
    }
  }, [id, storeJunctions]);

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => (prev > 0 ? prev - 1 : 35));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const handleQuickAction = async (action: string) => {
    if (action === "sync") {
      toast.success("Edge node config synchronized with master coordinator.");
    } else if (action === "flash") {
      if (id) {
        try {
          await api.signals.override(id, "FLASH_ALL_RED");
          toast.success("EMERGENCY ALL-RED override engaged on junction controller!");
        } catch {
          toast.success("ALL-RED override engaged locally.");
        }
      }
    } else {
      toast.success(`Action executed: ${action}`);
    }
  };

  const jName = junctionData?.name || "Connaught Place Outer Circle";

  return (
    <div className="p-6 space-y-6 animate-in fade-in duration-500">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <button
            onClick={() => navigate('/app/junctions')}
            className="flex items-center text-xs font-semibold text-slate-500 hover:text-teal-700 transition-colors mb-1"
          >
            <ChevronLeft className="w-4 h-4 mr-0.5" /> Back to Network
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold font-syne text-slate-900">{jName}</h1>
            <span className="flex items-center text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse mr-1.5" />
              LIVE TELEMETRY
            </span>
          </div>
          <p className="text-xs font-mono text-slate-400 mt-1">NODE-ID: {id || "DEL-CP-01"}</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => handleQuickAction("sync")}
            className="flex items-center gap-2 px-3.5 py-2 bg-white border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-sm"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Sync Config</span>
          </button>
          <button
            onClick={() => handleQuickAction("flash")}
            className="flex items-center gap-2 px-3.5 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-bold shadow-sm"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Flash All-Red</span>
          </button>
        </div>
      </div>

      {/* Main Layout: 2-column */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left 2 Cols: Edge Vision & Phase Visualizer */}
        <div className="lg:col-span-2 space-y-6">

          {/* Camera Feed with YOLOv8 bounding boxes */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
            <div className="flex justify-between items-center mb-3">
              <div className="flex items-center gap-2">
                <Video className="w-4 h-4 text-teal-600" />
                <h3 className="text-sm font-semibold text-slate-800">Edge Camera 01 (North Approach)</h3>
              </div>
              <div className="flex gap-2">
                <span className="text-[10px] font-mono font-bold bg-slate-100 text-slate-600 px-2 py-0.5 rounded">30 FPS</span>
                <span className="text-[10px] font-mono font-bold bg-teal-50 text-teal-700 border border-teal-200 px-2 py-0.5 rounded">YOLOv8 Edge Neural Net</span>
              </div>
            </div>

            <div className="relative bg-gradient-to-br from-slate-800 to-slate-900 rounded-xl aspect-video overflow-hidden border border-slate-700 flex items-center justify-center shadow-inner">
              <div className="absolute top-4 left-4 text-xs font-mono text-emerald-400 bg-slate-900/80 px-2 py-1 rounded">
                ● CAM_01_FEED_ONLINE
              </div>

              {/* Simulated Bounding Boxes */}
              <div className="absolute top-[25%] left-[20%] w-24 h-16 border-2 border-emerald-400 bg-emerald-400/10 rounded flex items-start p-1">
                <span className="text-[9px] font-mono font-bold text-white bg-emerald-500 px-1 rounded">CAR 0.94</span>
              </div>
              <div className="absolute top-[35%] right-[25%] w-32 h-20 border-2 border-sky-400 bg-sky-400/10 rounded flex items-start p-1">
                <span className="text-[9px] font-mono font-bold text-white bg-sky-500 px-1 rounded">BUS 0.89</span>
              </div>
              <div className="absolute bottom-[20%] left-[45%] w-14 h-12 border-2 border-amber-400 bg-amber-400/10 rounded flex items-start p-1">
                <span className="text-[9px] font-mono font-bold text-white bg-amber-500 px-1 rounded">2W 0.92</span>
              </div>
              <div className="absolute bottom-[30%] right-[15%] w-20 h-16 border-2 border-purple-400 bg-purple-400/10 rounded flex items-start p-1">
                <span className="text-[9px] font-mono font-bold text-white bg-purple-500 px-1 rounded">AUTO 0.87</span>
              </div>

              <div className="text-center text-slate-500 text-xs font-mono">
                [ LIVE RTSP STREAM — ON-DEVICE PCU INFERENCE ACTIVE ]
              </div>
            </div>
          </div>

          {/* Phase Visualizer */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-800">Adaptive Phase Visualizer</h3>
                <p className="text-xs text-slate-500">Mode: {signalPlan?.mode || "MARL Dynamic AI"}</p>
              </div>
              <span className="text-xs font-mono font-bold text-teal-600 bg-teal-50 px-2.5 py-1 rounded">
                Cycle: {signalPlan?.cycle_length_s || 120}s
              </span>
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-around gap-6 py-4 bg-slate-50 rounded-xl border border-slate-100">
              <div className="text-center">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Phase 1: North-South Straight</div>
                <div className="w-24 h-24 rounded-full bg-teal-600 text-white flex flex-col items-center justify-center font-mono shadow-md mx-auto">
                  <span className="text-3xl font-bold">{countdown}s</span>
                  <span className="text-[9px] uppercase tracking-wider font-bold">Green Hold</span>
                </div>
              </div>

              <div className="space-y-2 text-xs font-mono text-slate-600">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                  <span>North Approach: Green (35s Split)</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                  <span>South Approach: Green (35s Split)</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
                  <span>East Approach: Red Hold</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
                  <span>West Approach: Red Hold</span>
                </div>
              </div>
            </div>
          </div>

        </div>

        {/* Right Col: Jetson Edge Node Telemetry */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-teal-600" />
                Edge Compute Hardware
              </h3>
              <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                ONLINE
              </span>
            </div>

            <div className="text-xs space-y-1 bg-slate-50 p-3 rounded-lg border border-slate-100 font-mono">
              <div className="text-slate-500">DEVICE: NVIDIA Jetson Orin AGX (32GB)</div>
              <div className="text-slate-500">EDGE-IP: 192.168.10.42</div>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <div className="flex justify-between text-slate-600 font-semibold mb-1">
                  <span>GPU Temperature</span>
                  <span className="font-mono text-slate-900">54°C</span>
                </div>
                <div className="w-full bg-slate-100 h-1.5 rounded-full">
                  <div className="bg-teal-600 h-1.5 rounded-full" style={{ width: '54%' }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-slate-600 font-semibold mb-1">
                  <span>Inference Latency</span>
                  <span className="font-mono text-slate-900">33.2 ms</span>
                </div>
                <div className="w-full bg-slate-100 h-1.5 rounded-full">
                  <div className="bg-emerald-500 h-1.5 rounded-full" style={{ width: '33%' }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-slate-600 font-semibold mb-1">
                  <span>Memory Allocated (32GB)</span>
                  <span className="font-mono text-slate-900">14.8 GB (46%)</span>
                </div>
                <div className="w-full bg-slate-100 h-1.5 rounded-full">
                  <div className="bg-teal-500 h-1.5 rounded-full" style={{ width: '46%' }} />
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-100 grid grid-cols-2 gap-2 text-xs">
              <div className="p-2 rounded bg-slate-50 border border-slate-100 text-center">
                <span className="text-[10px] text-slate-400 block">MQTT Ping</span>
                <span className="font-mono font-bold text-teal-700">12 ms</span>
              </div>
              <div className="p-2 rounded bg-slate-50 border border-slate-100 text-center">
                <span className="text-[10px] text-slate-400 block">Uplink Rate</span>
                <span className="font-mono font-bold text-slate-800">4.2 Mbps</span>
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* Bottom Approaches Telemetry */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">Approach Lane Telemetry & PCU Split</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {approaches.map((app, i) => (
            <div key={i} className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-4 space-y-3">
              <div className="flex justify-between items-start">
                <div>
                  <div className="font-bold text-sm text-slate-800">{app.label}</div>
                  <div className="text-[11px] text-slate-400 font-mono">Approach {app.direction}</div>
                </div>
                <span className={clsx(
                  "px-2 py-0.5 rounded text-[10px] font-bold uppercase",
                  app.status === 'FLOWING' && "bg-emerald-50 text-emerald-700",
                  app.status === 'CONGESTED' && "bg-red-50 text-red-700",
                  app.status === 'HIGH_VOL' && "bg-amber-50 text-amber-700",
                  app.status === 'NORMAL' && "bg-slate-100 text-slate-700"
                )}>
                  {app.status}
                </span>
              </div>

              <div className="flex justify-between items-end">
                <div>
                  <span className="text-[10px] text-slate-400 uppercase block">Flow Rate</span>
                  <span className="text-xl font-mono font-bold text-slate-900">{app.pcu}</span>
                  <span className="text-xs text-slate-500 ml-1">PCU/h</span>
                </div>
                <div className="text-right text-xs font-mono text-slate-600">
                  <div>Spd: {app.speed} km/h</div>
                  <div>Que: {app.queueLength}m</div>
                </div>
              </div>

              {/* Progress split */}
              <div className="w-full bg-slate-100 h-1.5 rounded-full flex overflow-hidden">
                {app.breakdown.map((b, idx) => (
                  <div key={idx} className={b.color} style={{ width: `${b.percent}%` }} title={`${b.type}: ${b.percent}%`} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
