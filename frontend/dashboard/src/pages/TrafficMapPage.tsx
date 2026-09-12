import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { Car, Gauge, Activity, ArrowRightLeft, AlertTriangle, Search, Zap, Siren, Play, Pause, SkipBack, SkipForward, CheckCircle2 } from 'lucide-react';
import clsx from 'clsx';
import { useTrafficStore } from '../store/trafficStore';
import { wsService } from '../services/websocket';
import { TelemetrySourceBadge } from '../components/TelemetrySourceBadge';

// Junction positions only (map pins need coordinates before any telemetry
// arrives). pcu/speed/queue/status are intentionally absent here — a pin
// renders no numbers until real WS telemetry supplies them (SN-012g).
const DEFAULT_JUNCTIONS = [
  { id: 'DEL-CP-01', name: 'Connaught Place Outer Circle', lat: 28.6315, lng: 77.2167 },
  { id: 'DEL-ITO-02', name: 'ITO Crossing - Vikas Marg', lat: 28.6295, lng: 77.2415 },
  { id: 'DEL-AIIMS-03', name: 'AIIMS Flyover - Ring Road', lat: 28.5672, lng: 77.2100 },
  { id: 'DEL-DHK-05', name: 'Dhaula Kuan Interchange', lat: 28.5918, lng: 77.1615 },
  { id: 'DEL-ASH-04', name: 'Ashram Chowk - Mathura Road', lat: 28.5714, lng: 77.2588 },
  { id: 'DEL-ISBT-07', name: 'Kashmere Gate ISBT', lat: 28.6665, lng: 77.2285 },
];

interface JunctionPin {
  id: string;
  name: string;
  lat: number;
  lng: number;
  status: 'normal' | 'congested' | null;
  isMarl: boolean;
  pcu: number | null;
  speed: number | null;
  queue: number | null;
  source: string | null;
}

interface FeedEvent {
  id: string;
  title: string;
  time: string;
  desc: string;
  icon: any;
  color: string;
  bg: string;
}

export default function TrafficMapPage() {
  const storeJunctions = useTrafficStore((state) => state.junctions);
  const [searchTerm, setSearchTerm] = useState('');
  const [time, setTime] = useState(new Date());
  const [isPlaying, setIsPlaying] = useState(true);

  // Live Dynamic Stream State (Synchronized with SUMO / Micro-Sim). Starts
  // null/unavailable — SN-012g: no numeric panel renders a value it hasn't
  // actually received from the backend.
  const [totalVehicles, setTotalVehicles] = useState<number | null>(null);
  const [avgSpeed, setAvgSpeed] = useState<number | null>(null);
  const [throughput, setThroughput] = useState<number | null>(null);
  const [networkLos, setNetworkLos] = useState<string | null>(null);
  const [activeAlerts, setActiveAlerts] = useState<number | null>(null);
  const [ribbonSource, setRibbonSource] = useState<string | null>(null);
  const [isTwinConnected, setIsTwinConnected] = useState(false);
  const [lastStepReceived, setLastStepReceived] = useState<number | null>(null);

  // Junction-level live telemetry — pcu/speed/queue/status/source stay null
  // until a WS message actually supplies them for that pin.
  const [junctionsData, setJunctionsData] = useState<JunctionPin[]>(
    DEFAULT_JUNCTIONS.map(j => ({ ...j, status: null, isMarl: false, pcu: null, speed: null, queue: null, source: null }))
  );

  // Live telemetry event feed, filled from the WebSocket channel below. It was
  // previously seeded with four invented events carrying relative timestamps
  // ("Just now", "2s ago"), so the feed always looked live — including a MARL
  // phase optimisation that no controller performed.
  const [feedEvents, setFeedEvents] = useState<FeedEvent[]>([]);

  // Connect to live WebSockets from backend. This ribbon reads the aggregate
  // SIMULATION_TICK shape (total_vehicles, junctions: [...], etc.) that
  // sumo_live_bridge.py publishes on REDIS_CHANNELS["simulation"] — it was
  // previously subscribed to 'traffic', which only ever carries a single
  // per-junction JunctionTelemetry object (no total_vehicles/junctions[]
  // array field), so none of these handlers were firing on real data before.
  useEffect(() => {
    wsService.connect('simulation');
    wsService.connect('signals');

    const unsubscribeTraffic = wsService.onMessage('simulation', (data: any) => {
      setIsTwinConnected(true);
      if (data.source !== undefined) {
        setRibbonSource(data.source);
      }
      if (data.step !== undefined) {
        setLastStepReceived(data.step);
      }
      if (data.total_vehicles !== undefined) {
        setTotalVehicles(data.total_vehicles);
      }
      if (data.avg_speed !== undefined) {
        setAvgSpeed(data.avg_speed);
      }
      if (data.throughput !== undefined) {
        setThroughput(data.throughput);
      }
      if (data.network_los !== undefined) {
        setNetworkLos(data.network_los);
      }
      if (data.active_alerts !== undefined) {
        setActiveAlerts(data.active_alerts);
      }

      // Update junction pins with real TraCI queues and speeds
      if (Array.isArray(data.junctions) && data.junctions.length > 0) {
        setJunctionsData(prev =>
          prev.map((j, idx) => {
            const sumoJ = data.junctions[idx % data.junctions.length];
            if (!sumoJ) return j;
            return {
              ...j,
              queue: sumoJ.queue,
              speed: sumoJ.speed,
              pcu: sumoJ.pcu,
              source: data.source ?? null,
              status: sumoJ.is_congested ? 'congested' : 'normal',
            };
          })
        );
      }

      // Add real-time TraCI telemetry event to live feed.
      // The same step can arrive more than once (overlapping broadcasts
      // across backend workers, WebSocket reconnects replaying a recent
      // message) — skip it rather than pushing a second feed entry with
      // the same id, which produced a real React "duplicate key" warning
      // and visibly duplicated rows in this feed.
      if (data.step && data.step % 10 === 0) {
        const stepId = `step-${data.step}`;
        setFeedEvents(prev => {
          if (prev.some(e => e.id === stepId)) return prev;
          const stepEvent: FeedEvent = {
            id: stepId,
            title: `TraCI Step ${data.step} Synced`,
            time: 'Just now',
            desc: `${data.total_vehicles} vehicles active | Avg ${data.avg_speed} km/h | LOS ${data.network_los}`,
            icon: Activity,
            color: 'text-sky-600',
            bg: 'bg-sky-50',
          };
          return [stepEvent, ...prev.slice(0, 5)];
        });
      }
    });

    const unsubscribeSignals = wsService.onMessage('signals', (data: any) => {
      if (data.action) {
        const newEvent: FeedEvent = {
          id: String(Date.now()),
          title: `Signal Override: ${data.action}`,
          time: 'Just now',
          desc: `Junction ${data.junction_id ? data.junction_id : 'Node'}: ${data.action}`,
          icon: Zap,
          color: 'text-teal-600',
          bg: 'bg-teal-50'
        };
        setFeedEvents(prev => [newEvent, ...prev.slice(0, 5)]);
      }
    });

    return () => {
      unsubscribeTraffic();
      unsubscribeSignals();
    };
  }, []);

  // Clock and fallback simulation pulse loop
  useEffect(() => {
    let timer: number;
    if (isPlaying) {
      timer = window.setInterval(() => {
        setTime(new Date());
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [isPlaying, isTwinConnected]);

  // Merge store junctions (real names/coords from the DB) with whatever live
  // telemetry has actually arrived over WS. No fabricated numeric fallback —
  // a junction with no live match renders with status/pcu/speed/queue = null.
  const baseJunctions: JunctionPin[] = storeJunctions && storeJunctions.length > 0
    ? storeJunctions.map((j, idx) => {
        const live = junctionsData[idx % junctionsData.length];
        return {
          id: j.id,
          name: j.name,
          lat: j.latitude,
          lng: j.longitude,
          status: live?.status ?? null,
          isMarl: live?.isMarl ?? false,
          pcu: live?.pcu ?? null,
          speed: live?.speed ?? null,
          queue: live?.queue ?? null,
          source: live?.source ?? null,
        };
      })
    : junctionsData;

  const filteredJunctions = baseJunctions.filter(j =>
    j.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    j.id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getMarkerColor = (status: string | null, isMarl: boolean) => {
    if (status === 'congested') return '#EF4444'; // Red-500
    if (status === null) return '#94A3B8'; // Slate-400 — no live status yet
    if (isMarl) return '#0D9488'; // Teal-600
    return '#10B981'; // Emerald-500
  };

  return (
    <div className="relative w-full h-full min-h-[calc(100vh-4rem)] bg-slate-100 overflow-hidden font-sans">
      {/* MAP LAYER */}
      <div className="absolute inset-0 z-0">
        <MapContainer 
          center={[28.6139, 77.2090]} 
          zoom={12} 
          style={{ height: '100%', width: '100%' }}
          zoomControl={false}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          />
          {filteredJunctions.map((j) => (
            <CircleMarker
              key={j.id}
              center={[j.lat, j.lng]}
              radius={j.status === 'congested' ? 11 : 9}
              pathOptions={{
                color: getMarkerColor(j.status, j.isMarl),
                fillColor: getMarkerColor(j.status, j.isMarl),
                fillOpacity: 0.85,
                weight: j.status === 'congested' ? 3 : 2
              }}
            >
              <Popup>
                <div className="font-sans p-1 min-w-[200px]">
                  <h3 className="font-bold text-slate-900 text-sm">{j.name}</h3>
                  <p className="text-[10px] text-slate-500 font-mono mt-0.5">{j.id}</p>
                  
                  <div className="mt-3 grid grid-cols-3 gap-1.5 text-center font-mono text-xs">
                    <div className="bg-slate-50 p-1.5 rounded border border-slate-100">
                      <div className="text-[9px] text-slate-400">FLOW</div>
                      <div className="font-bold text-slate-800">{j.pcu ?? '—'}</div>
                    </div>
                    <div className="bg-slate-50 p-1.5 rounded border border-slate-100">
                      <div className="text-[9px] text-slate-400">SPEED</div>
                      <div className="font-bold text-teal-600">{j.speed !== null ? `${j.speed}k` : '—'}</div>
                    </div>
                    <div className="bg-slate-50 p-1.5 rounded border border-slate-100">
                      <div className="text-[9px] text-slate-400">QUEUE</div>
                      <div className={clsx("font-bold", (j.queue ?? 0) > 40 ? "text-red-600" : "text-emerald-600")}>
                        {j.queue !== null ? `${j.queue}m` : '—'}
                      </div>
                    </div>
                  </div>

                  <div className="mt-2.5 flex items-center justify-between pt-2 border-t border-slate-100">
                    <div className="flex items-center gap-1.5">
                      {j.status && (
                        <span className={clsx(
                          "px-2 py-0.5 rounded-full text-[10px] font-bold uppercase",
                          j.status === 'congested' ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"
                        )}>
                          {j.status}
                        </span>
                      )}
                      <TelemetrySourceBadge source={j.source} showIcon={false} />
                    </div>
                    {j.isMarl && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-teal-100 text-teal-700 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-teal-600 animate-pulse" />
                        MARL Active
                      </span>
                    )}
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      {/* TOP METRIC RIBBON - FULLY DYNAMIC LIVE DATA */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 flex items-center space-x-3 w-max">
        {/* Connection Status Badge */}
        <div className={clsx(
          "bg-white/95 backdrop-blur-md rounded-xl border shadow-xl px-3.5 py-3 flex items-center space-x-2.5 transition-all",
          isTwinConnected ? "border-emerald-300" : "border-amber-300"
        )}>
          <div className={clsx(
            "w-2.5 h-2.5 rounded-full shrink-0",
            isTwinConnected ? "bg-emerald-500 animate-ping" : "bg-amber-500 animate-pulse"
          )} />
          <div>
            <div className={clsx("text-[9px] font-bold uppercase tracking-widest font-mono", isTwinConnected ? "text-emerald-700" : "text-amber-700")}>
              SUMO DIGITAL TWIN
            </div>
            <div className="text-xs font-mono font-bold text-slate-800">
              {isTwinConnected ? `STREAM: LIVE (Step ${lastStepReceived ?? 0})` : "STANDALONE SIM"}
            </div>
          </div>
        </div>

        {/* Dynamic Metric Cards — SN-012g: no fabricated value or trend, "—" until real data arrives */}
        {[
          { label: 'Active Vehicles', value: totalVehicles !== null ? totalVehicles.toLocaleString() : '—', icon: Car },
          { label: 'Corridor Speed', value: avgSpeed !== null ? `${avgSpeed} km/h` : '—', icon: Gauge },
          { label: 'Network LOS', value: networkLos ?? '—', icon: Activity },
          { label: 'Throughput', value: throughput !== null ? `${throughput.toLocaleString()} PCU/h` : '—', icon: ArrowRightLeft },
        ].map((metric, i) => (
          <div key={i} className="bg-white/95 backdrop-blur-md rounded-xl border border-white/80 shadow-xl px-4 py-3 flex items-center space-x-3 transition-all">
            <metric.icon className="w-5 h-5 text-slate-400" />
            <div>
              <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{metric.label}</div>
              <div className="font-mono font-bold text-slate-900 text-sm flex items-center space-x-2">
                <span className="tabular-nums">{metric.value}</span>
              </div>
            </div>
          </div>
        ))}

        <TelemetrySourceBadge source={ribbonSource} />

        <div className="bg-red-500/95 backdrop-blur-md rounded-xl border border-red-400 shadow-xl px-4 py-3 flex items-center space-x-3 text-white">
          <AlertTriangle className="w-5 h-5" />
          <div>
            <div className="text-[10px] font-semibold text-red-100 uppercase tracking-wider">Active Alerts</div>
            <div className="font-mono font-bold text-white text-sm">{activeAlerts !== null ? `${activeAlerts} Critical` : '—'}</div>
          </div>
        </div>
      </div>

      {/* LEFT PANEL: FILTERS & AI */}
      <div className="absolute top-24 left-4 z-20 w-80 space-y-4">
        <div className="bg-white/95 backdrop-blur-md rounded-xl border border-white shadow-xl p-5">
          <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider flex items-center mb-4">
            <Search className="w-4 h-4 mr-2 text-slate-400" />
            Network Filters
          </h2>
          <div className="relative mb-6">
            <input 
              type="text" 
              placeholder="Search junctions..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 font-medium"
            />
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
          </div>

          <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3">Status Overlays</h3>
          <div className="space-y-3 mb-6">
            <label className="flex items-center space-x-3 cursor-pointer group">
              <div className="w-4 h-4 rounded border border-slate-300 flex items-center justify-center group-hover:border-teal-500 bg-teal-500">
                <CheckCircle2 className="w-3 h-3 text-white" />
              </div>
              <span className="text-sm font-medium text-slate-700">Congested Routes</span>
              <div className="ml-auto w-2 h-2 rounded-full bg-red-500"></div>
            </label>
            <label className="flex items-center space-x-3 cursor-pointer group">
              <div className="w-4 h-4 rounded border border-slate-300 flex items-center justify-center group-hover:border-teal-500 bg-teal-500">
                <CheckCircle2 className="w-3 h-3 text-white" />
              </div>
              <span className="text-sm font-medium text-slate-700">Emergency Corridors</span>
              <Siren className="ml-auto w-4 h-4 text-blue-500" />
            </label>
          </div>

          <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3">AI Control Systems</h3>
          <div className="bg-teal-50 border border-teal-100 rounded-lg p-3">
            <div className="flex items-center space-x-2 mb-1">
              <Zap className="w-4 h-4 text-teal-600" />
              <span className="font-bold text-teal-800 text-sm">MARL Adaptive Control</span>
            </div>
            <p className="text-xs text-teal-700 font-medium leading-relaxed">
              Decentralized Deep Q-Network actively minimizing queue wait-times across 12 smart nodes.
            </p>
          </div>

          <div className="mt-5 flex space-x-2">
            {['Satellite', 'Light', 'Heatmap'].map((layer, i) => (
              <button 
                key={layer}
                className={clsx(
                  "flex-1 py-1.5 px-2 rounded-md text-xs font-bold transition-colors",
                  i === 1 ? "bg-teal-600 text-white shadow-xs" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                )}
              >
                {layer}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* RIGHT PANEL: LIVE TELEMETRY FEED */}
      <div className="absolute top-24 right-4 z-20 w-80">
        <div className="bg-white/95 backdrop-blur-md rounded-xl border border-white shadow-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider flex items-center">
              <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse mr-2" />
              Live Telemetry Feed
            </h2>
            <span className="text-[10px] font-mono text-emerald-600 font-bold">10Hz LIVE</span>
          </div>

          <div className="space-y-3 max-h-[460px] overflow-y-auto pr-1">
            {feedEvents.map((event) => (
              <div key={event.id} className="flex items-start space-x-3 p-2 rounded-lg hover:bg-slate-50 transition-colors animate-in fade-in duration-300 border border-slate-100/60">
                <div className={clsx("w-8 h-8 rounded-full flex items-center justify-center shrink-0", event.bg)}>
                  <event.icon className={clsx("w-4 h-4", event.color)} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-slate-800 truncate">{event.title}</h4>
                  </div>
                  <p className="text-[11px] text-slate-500 mt-0.5 leading-tight">{event.desc}</p>
                  <p className="text-[9px] font-mono text-slate-400 mt-1">{event.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* BOTTOM PLAYBACK BAR */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 w-[640px]">
        <div className="bg-white/95 backdrop-blur-md rounded-xl border border-white/80 shadow-2xl px-6 py-4 flex items-center space-x-6">
          <div className="flex items-center space-x-2 shrink-0">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-bold text-slate-800 tracking-wider">LIVE OPS</span>
          </div>

          <div className="flex items-center space-x-3 text-slate-600 shrink-0">
            <button className="p-1.5 hover:bg-slate-100 rounded-full transition-colors"><SkipBack className="w-4 h-4" /></button>
            <button 
              className="w-9 h-9 flex items-center justify-center bg-teal-600 text-white rounded-full hover:bg-teal-700 shadow-md transition-colors"
              onClick={() => setIsPlaying(!isPlaying)}
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
            </button>
            <button className="p-1.5 hover:bg-slate-100 rounded-full transition-colors"><SkipForward className="w-4 h-4" /></button>
          </div>

          <div className="flex-1 flex items-center space-x-4">
            <div className="h-1.5 w-full bg-slate-200 rounded-full overflow-hidden relative cursor-pointer">
              <div className="absolute top-0 left-0 h-full w-[95%] bg-teal-500 rounded-full"></div>
              <div className="absolute top-1/2 -translate-y-1/2 right-[5%] w-3 h-3 bg-white border-2 border-teal-500 rounded-full shadow"></div>
            </div>
          </div>

          <div className="flex items-center space-x-4 shrink-0 font-mono">
            <div className="text-sm font-bold text-slate-800 tabular-nums">
              {time.toLocaleTimeString('en-US', { hour12: false })}
            </div>
            <div className="px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded text-xs font-bold">
              1x LIVE
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
