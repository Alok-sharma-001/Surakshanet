import { useState, useEffect } from 'react';
import { Cpu, RefreshCw, Settings, AlertTriangle, ArrowDown, ArrowLeft, ArrowUp, ArrowRight, Wifi, Video, Activity, Clock } from 'lucide-react';
import { clsx } from 'clsx';

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

const APPROACHES: ApproachData[] = [
  {
    direction: 'NORTH',
    label: 'North Bound',
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
    label: 'East Bound',
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
    label: 'South Bound',
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
    label: 'West Bound',
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

const StatusBadge = ({ status }: { status: ApproachData['status'] }) => {
  const config = {
    NORMAL: { bg: 'bg-slate-100', text: 'text-slate-600', label: 'NORMAL' },
    FLOWING: { bg: 'bg-emerald-50', text: 'text-emerald-600', label: 'FLOWING' },
    CONGESTED: { bg: 'bg-red-50', text: 'text-red-600', label: 'CONGESTED' },
    HIGH_VOL: { bg: 'bg-amber-50', text: 'text-amber-600', label: 'HIGH VOL' },
  };
  const c = config[status];
  return (
    <span className={clsx("px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide", c.bg, c.text)}>
      {c.label}
    </span>
  );
};

export default function JunctionDetailPage() {
  const [countdown, setCountdown] = useState(14);

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => (prev > 0 ? prev - 1 : 120)); // Reset to full cycle for demo
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex flex-col h-full space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">
            CENTRAL DISTRICT <span className="text-slate-300">›</span> <span className="font-mono">JID: BLR-CEN-042</span>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-syne font-bold text-slate-900">MG Road - Brigade Junction</h1>
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 text-emerald-700 rounded-full border border-emerald-100">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
              <span className="text-[10px] font-bold uppercase tracking-wider">Live</span>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          <button className="px-4 py-2 bg-white border border-[#E2E8F0] rounded-lg text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition-colors flex items-center gap-2">
            <Settings className="w-4 h-4" /> Signal Config
          </button>
          <button className="px-4 py-2 bg-white border border-[#E2E8F0] rounded-lg text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition-colors flex items-center gap-2">
            <Clock className="w-4 h-4" /> History
          </button>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2/3) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Camera Feed */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                <Video className="w-4 h-4 text-slate-400" />
                Cam 01: North Approach (Edge Processing)
              </h3>
              <div className="flex gap-2">
                <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px] font-bold uppercase flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span> 30 FPS
                </span>
                <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px] font-bold uppercase flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span> YOLOv8s
                </span>
              </div>
            </div>
            
            <div className="bg-gradient-to-br from-slate-200 to-slate-300 rounded-lg aspect-[16/9] relative overflow-hidden flex items-center justify-center border border-slate-200">
               <div className="absolute inset-0 opacity-10" style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, black 1px, transparent 0)', backgroundSize: '24px 24px' }}></div>
               <span className="text-slate-400 font-medium mix-blend-color-burn">Simulated Live Feed</span>

               {/* Bounding Boxes */}
               <div className="absolute top-[30%] left-[20%] w-[15%] h-[20%] border-2 border-emerald-500 bg-emerald-500/10 rounded-sm">
                  <div className="absolute -top-5 left-[-2px] bg-emerald-500 text-white text-[9px] font-bold px-1 py-0.5 rounded-sm whitespace-nowrap">CAR 0.92</div>
               </div>
               
               <div className="absolute top-[45%] left-[55%] w-[25%] h-[35%] border-2 border-blue-500 bg-blue-500/10 rounded-sm">
                  <div className="absolute -top-5 left-[-2px] bg-blue-500 text-white text-[9px] font-bold px-1 py-0.5 rounded-sm whitespace-nowrap">BUS 0.88</div>
               </div>

               <div className="absolute top-[60%] left-[30%] w-[8%] h-[15%] border-2 border-orange-500 bg-orange-500/10 rounded-sm">
                  <div className="absolute -top-5 left-[-2px] bg-orange-500 text-white text-[9px] font-bold px-1 py-0.5 rounded-sm whitespace-nowrap">2W 0.95</div>
               </div>
            </div>
          </div>

          {/* Live Phase Visualizer */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-sm font-semibold text-slate-800">Live Phase Visualizer</h3>
              <div className="text-xs text-slate-500 font-medium">
                Cycle: <span className="font-mono text-slate-700 font-bold">120s</span> <span className="mx-2 text-slate-300">|</span> 
                Phase: <span className="font-semibold text-teal-600">North-South Straight</span>
              </div>
            </div>

            <div className="h-64 bg-slate-50 rounded-lg border border-slate-100 flex items-center justify-center relative overflow-hidden">
               {/* Roads */}
               <div className="absolute top-0 bottom-0 left-1/2 -ml-12 w-24 bg-slate-200">
                 {/* Dashed line */}
                 <div className="absolute top-0 bottom-0 left-1/2 w-0.5 bg-white border-dashed border-l-2 border-white"></div>
               </div>
               <div className="absolute left-0 right-0 top-1/2 -mt-12 h-24 bg-slate-200">
                  {/* Dashed line */}
                 <div className="absolute left-0 right-0 top-1/2 h-0.5 bg-white border-dashed border-t-2 border-white"></div>
               </div>

               {/* Intersection Center Square to hide dashed lines overlapping */}
               <div className="absolute w-24 h-24 bg-slate-200"></div>

               {/* Signals */}
               {/* North Signal (Green) */}
               <div className="absolute top-[20px] left-[50%] ml-14 w-3 h-8 bg-slate-800 rounded flex flex-col items-center justify-around py-0.5">
                 <div className="w-1.5 h-1.5 rounded-full bg-red-900/40"></div>
                 <div className="w-1.5 h-1.5 rounded-full bg-amber-900/40"></div>
                 <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]"></div>
               </div>
               
               {/* South Signal (Green) */}
               <div className="absolute bottom-[20px] right-[50%] mr-14 w-3 h-8 bg-slate-800 rounded flex flex-col items-center justify-around py-0.5">
                 <div className="w-1.5 h-1.5 rounded-full bg-red-900/40"></div>
                 <div className="w-1.5 h-1.5 rounded-full bg-amber-900/40"></div>
                 <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]"></div>
               </div>

               {/* East Signal (Red) */}
               <div className="absolute right-[20px] top-[50%] -mt-10 h-3 w-8 bg-slate-800 rounded flex items-center justify-around px-0.5">
                 <div className="w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"></div>
                 <div className="w-1.5 h-1.5 rounded-full bg-amber-900/40"></div>
                 <div className="w-1.5 h-1.5 rounded-full bg-emerald-900/40"></div>
               </div>

               {/* West Signal (Red) */}
               <div className="absolute left-[20px] bottom-[50%] -mb-10 h-3 w-8 bg-slate-800 rounded flex items-center justify-around px-0.5 flex-row-reverse">
                 <div className="w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"></div>
                 <div className="w-1.5 h-1.5 rounded-full bg-amber-900/40"></div>
                 <div className="w-1.5 h-1.5 rounded-full bg-emerald-900/40"></div>
               </div>

               {/* Central Countdown */}
               <div className="absolute w-16 h-16 bg-white rounded-full shadow-lg border-4 border-teal-500 flex items-center justify-center z-10">
                 <span className="text-2xl font-mono font-bold text-teal-600">{countdown}s</span>
               </div>
            </div>
          </div>
        </div>

        {/* Right Column (1/3) */}
        <div className="space-y-6">
          {/* Edge Node Status */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
             <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-slate-400" />
                Edge Node Status
              </h3>
              <div className="flex items-center gap-1.5">
                 <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
                 <span className="text-[10px] font-bold text-emerald-600 uppercase tracking-wider">Online</span>
              </div>
             </div>
             <div className="mb-5">
               <div className="text-sm font-medium text-slate-900">Jetson Orin AGX</div>
               <div className="text-xs font-mono text-slate-500">ID: BLR-NODE-8821</div>
             </div>

             <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-xs font-medium text-slate-600 mb-1">
                    <span>GPU Temperature</span>
                    <span className="font-mono">54°C</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 rounded-full" style={{ width: '55%' }}></div>
                  </div>
                </div>
                
                <div>
                  <div className="flex justify-between text-xs font-medium text-slate-600 mb-1">
                    <span>Inference Rate</span>
                    <span className="font-mono text-teal-600 font-bold">30 FPS</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-teal-500 rounded-full" style={{ width: '100%' }}></div>
                  </div>
                </div>
                
                <div>
                  <div className="flex justify-between text-xs font-medium text-slate-600 mb-1">
                    <span>Memory Usage (32GB)</span>
                    <span className="font-mono">18.4 GB</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 rounded-full" style={{ width: '57%' }}></div>
                  </div>
                </div>
             </div>

             <div className="mt-6 pt-5 border-t border-slate-100 grid grid-cols-2 gap-4">
               <div>
                 <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider flex items-center gap-1 mb-1">
                   <Activity className="w-3 h-3" /> MQTT Latency
                 </div>
                 <div className="text-lg font-mono font-medium text-slate-800">12ms</div>
               </div>
               <div>
                 <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider flex items-center gap-1 mb-1">
                   <Wifi className="w-3 h-3" /> Uplink
                 </div>
                 <div className="text-lg font-mono font-medium text-slate-800">4.2 mbps</div>
               </div>
             </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-slate-50 rounded-xl border border-[#E2E8F0] shadow-sm p-4">
             <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Quick Actions</h3>
             <div className="grid grid-cols-2 gap-3">
               <button className="flex flex-col items-center justify-center p-3 bg-white rounded-lg border border-slate-200 shadow-sm hover:border-slate-300 hover:shadow transition-all group">
                 <RefreshCw className="w-5 h-5 text-slate-400 group-hover:text-blue-500 mb-2 transition-colors" />
                 <span className="text-[11px] font-semibold text-slate-600">Restart Node</span>
               </button>
               <button className="flex flex-col items-center justify-center p-3 bg-white rounded-lg border border-slate-200 shadow-sm hover:border-slate-300 hover:shadow transition-all group">
                 <RefreshCw className="w-5 h-5 text-slate-400 group-hover:text-teal-500 mb-2 transition-colors" />
                 <span className="text-[11px] font-semibold text-slate-600">Sync Config</span>
               </button>
               <button className="flex flex-col items-center justify-center p-3 bg-white rounded-lg border border-slate-200 shadow-sm hover:border-red-300 hover:shadow transition-all group col-span-2">
                 <AlertTriangle className="w-5 h-5 text-red-400 group-hover:text-red-600 mb-2 transition-colors" />
                 <span className="text-[11px] font-semibold text-slate-600 group-hover:text-red-600">Flash All Red (Emergency)</span>
               </button>
             </div>
          </div>
        </div>
      </div>

      {/* Bottom Section: Approach Telemetry */}
      <div className="pt-2">
        <h2 className="text-sm font-semibold text-slate-800 mb-3">Approach Telemetry</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {APPROACHES.map((app) => (
            <div key={app.direction} className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-4">
               <div className="flex justify-between items-start mb-4">
                 <div className="flex items-center gap-2">
                   <div className="p-1.5 bg-slate-50 rounded-md border border-slate-100 text-slate-500">
                     <app.icon className="w-4 h-4" />
                   </div>
                   <span className="text-sm font-semibold text-slate-800">{app.label}</span>
                 </div>
                 <StatusBadge status={app.status} />
               </div>

               <div className="flex items-end gap-2 mb-4">
                 <span className="text-2xl font-syne font-bold text-slate-900 leading-none">{app.pcu}</span>
                 <span className="text-xs text-slate-500 font-medium mb-0.5">PCU/hr</span>
               </div>

               {/* Breakdown Bar */}
               <div className="h-2 w-full flex rounded-full overflow-hidden mb-2">
                 {app.breakdown.map((item, i) => (
                   <div key={i} className={clsx("h-full", item.color)} style={{ width: `${item.percent}%` }} title={`${item.type}: ${item.percent}%`}></div>
                 ))}
               </div>
               
               {/* Breakdown Legend */}
               <div className="flex gap-3 mb-5">
                 {app.breakdown.map((item, i) => (
                   <div key={i} className="flex items-center gap-1 text-[10px] font-medium text-slate-500">
                     <span className={clsx("w-1.5 h-1.5 rounded-full", item.color)}></span> {item.type} {item.percent}%
                   </div>
                 ))}
               </div>

               <div className="grid grid-cols-2 gap-2 pt-3 border-t border-slate-100">
                 <div>
                   <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">Queue</div>
                   <div className={clsx(
                     "text-sm font-mono font-medium",
                     app.queueLength > 50 ? "text-red-600 font-bold" : "text-slate-700"
                   )}>{app.queueLength}m</div>
                 </div>
                 <div>
                   <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">Avg Speed</div>
                   <div className={clsx(
                     "text-sm font-mono font-medium",
                     app.speed < 15 ? "text-red-600 font-bold" : "text-slate-700"
                   )}>{app.speed} km/h</div>
                 </div>
               </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
