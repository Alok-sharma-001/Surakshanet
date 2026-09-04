import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { Car, Gauge, Activity, ArrowRightLeft, AlertTriangle, Search, Zap, Siren, MoreVertical, Play, Pause, SkipBack, SkipForward, CheckCircle2 } from 'lucide-react';
import clsx from 'clsx';
import { useTrafficStore } from '../store/trafficStore';

// Fallback Default Junctions for Delhi
const DEFAULT_JUNCTIONS = [
  { id: 'DEL-CP-01', name: 'Connaught Place', lat: 28.6315, lng: 77.2167, status: 'normal', isMarl: true },
  { id: 'DEL-ITO-02', name: 'ITO Intersection', lat: 28.6295, lng: 77.2415, status: 'normal', isMarl: false },
  { id: 'DEL-AIIMS-03', name: 'AIIMS Crossing', lat: 28.5672, lng: 77.2100, status: 'congested', isMarl: true },
  { id: 'DEL-DHK-05', name: 'Dhaula Kuan', lat: 28.5918, lng: 77.1615, status: 'congested', isMarl: true },
  { id: 'DEL-ASH-04', name: 'Ashram Chowk', lat: 28.5714, lng: 77.2588, status: 'congested', isMarl: true },
  { id: 'DEL-ISBT-07', name: 'Kashmere Gate', lat: 28.6665, lng: 77.2285, status: 'normal', isMarl: true },
];

export default function TrafficMapPage() {
  const storeJunctions = useTrafficStore((state) => state.junctions);
  const [searchTerm, setSearchTerm] = useState('');
  const [time, setTime] = useState(new Date());
  const [isPlaying, setIsPlaying] = useState(true);

  // Map backend database junctions when loaded, else use defaults
  const junctions = storeJunctions && storeJunctions.length > 0
    ? storeJunctions.map((j, idx) => ({
        id: j.id,
        name: j.name,
        lat: j.latitude,
        lng: j.longitude,
        status: idx % 3 === 0 ? 'congested' : 'normal',
        isMarl: idx % 2 === 0
      }))
    : DEFAULT_JUNCTIONS;

  const filteredJunctions = junctions.filter(j =>
    j.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    j.id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  useEffect(() => {
    let timer: number;
    if (isPlaying) {
      timer = window.setInterval(() => {
        setTime(new Date());
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [isPlaying]);

  const getMarkerColor = (status: string, isMarl: boolean) => {
    if (status === 'congested') return '#EF4444'; // red-500
    if (isMarl) return '#0D9488'; // teal-600
    return '#10B981'; // emerald-500
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
              radius={8}
              pathOptions={{
                color: getMarkerColor(j.status, j.isMarl),
                fillColor: getMarkerColor(j.status, j.isMarl),
                fillOpacity: 0.8,
                weight: 2
              }}
            >
              <Popup>
                <div className="font-sans">
                  <h3 className="font-bold text-slate-800">{j.name}</h3>
                  <p className="text-xs text-slate-500 font-mono mt-1">{j.id}</p>
                  <div className="mt-2 flex items-center space-x-2">
                    <span className={clsx(
                      "px-2 py-0.5 rounded-full text-[10px] font-bold uppercase",
                      j.status === 'congested' ? "bg-red-100 text-red-600" : "bg-emerald-100 text-emerald-600"
                    )}>
                      {j.status}
                    </span>
                    {j.isMarl && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-teal-100 text-teal-600">
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

      {/* TOP METRIC RIBBON */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 flex items-center space-x-3 w-max">
        {[
          { label: 'Total Vehicles', value: '24,510', trend: '↑2.4%', trendColor: 'text-emerald-500', icon: Car },
          { label: 'Avg Speed', value: '32 km/h', icon: Gauge },
          { label: 'Network LOS', value: 'C Fair Flow', icon: Activity },
          { label: 'Throughput', value: '1,200 PCU/hr', icon: ArrowRightLeft },
        ].map((metric, i) => (
          <div key={i} className="bg-white/90 backdrop-blur-sm rounded-xl border border-white/60 shadow-lg px-4 py-3 flex items-center space-x-3">
            <metric.icon className="w-5 h-5 text-slate-400" />
            <div>
              <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{metric.label}</div>
              <div className="font-mono font-bold text-slate-800 text-sm flex items-center space-x-2">
                <span>{metric.value}</span>
                {metric.trend && <span className={`text-xs ${metric.trendColor}`}>{metric.trend}</span>}
              </div>
            </div>
          </div>
        ))}
        <div className="bg-red-500/90 backdrop-blur-sm rounded-xl border border-red-400 shadow-lg px-4 py-3 flex items-center space-x-3 text-white">
          <AlertTriangle className="w-5 h-5" />
          <div>
            <div className="text-[10px] font-semibold text-red-100 uppercase tracking-wider">Active Alerts</div>
            <div className="font-mono font-bold text-white text-sm">5 Critical</div>
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
              className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
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
              <span className="text-sm font-medium text-slate-700">Emergency Vehicles</span>
              <Siren className="ml-auto w-3 h-3 text-blue-500" />
            </label>
          </div>

          <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3">AI Control Systems</h3>
          <div className="bg-teal-50 border border-teal-100 rounded-lg p-3">
            <div className="flex items-center space-x-2 mb-1">
              <Zap className="w-4 h-4 text-teal-600" />
              <span className="font-bold text-teal-800 text-sm">MARL Active</span>
            </div>
            <p className="text-xs text-teal-600 font-medium">Multi-Agent Reinforcement Learning controlling 42/150 junctions.</p>
          </div>

          <div className="mt-6 flex space-x-2">
            {['Satellite', 'Light', 'Heatmap'].map((layer, i) => (
              <button 
                key={layer}
                className={clsx(
                  "flex-1 py-1.5 px-2 rounded-md text-xs font-bold transition-colors",
                  i === 1 ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                )}
              >
                {layer}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* RIGHT PANEL: TELEMETRY FEED */}
      <div className="absolute top-24 right-4 z-20 w-80">
        <div className="bg-white/95 backdrop-blur-md rounded-xl border border-white shadow-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider flex items-center">
              <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse mr-2" />
              Live Telemetry Feed
            </h2>
            <MoreVertical className="w-4 h-4 text-slate-400 cursor-pointer" />
          </div>

          <div className="space-y-3">
            {[
              { title: 'Ambulance Approaching', time: 'Just now', desc: 'J-42 pre-empted to Green', icon: Siren, color: 'text-red-500', bg: 'bg-red-50' },
              { title: 'MARL Phase Adjustment', time: '~2m', desc: 'Corridor Alpha cycle increased', icon: Zap, color: 'text-sky-500', bg: 'bg-sky-50' },
              { title: 'Congestion Build-up', time: '~5m', desc: 'Volume exceeding capacity', icon: AlertTriangle, color: 'text-amber-500', bg: 'bg-amber-50' },
              { title: 'Sync Check Complete', time: '~12m', desc: 'All 150 edge devices nominal', icon: CheckCircle2, color: 'text-emerald-500', bg: 'bg-emerald-50' },
            ].map((event, i) => (
              <div key={i} className="flex items-start space-x-3 p-2 rounded-lg hover:bg-slate-50 transition-colors">
                <div className={clsx("w-8 h-8 rounded-full flex items-center justify-center shrink-0", event.bg)}>
                  <event.icon className={clsx("w-4 h-4", event.color)} />
                </div>
                <div>
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-slate-800">{event.title}</h4>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">{event.desc}</p>
                  <p className="text-[10px] font-mono text-slate-400 mt-1">{event.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* BOTTOM PLAYBACK BAR */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 w-[600px]">
        <div className="bg-white/90 backdrop-blur-md rounded-xl border border-white/60 shadow-xl px-6 py-4 flex items-center space-x-6">
          <div className="flex items-center space-x-2 shrink-0">
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-xs font-bold text-slate-700 tracking-wider">LIVE OPS</span>
          </div>

          <div className="flex items-center space-x-3 text-slate-600 shrink-0">
            <button className="p-1 hover:bg-slate-100 rounded-full transition-colors"><SkipBack className="w-4 h-4" /></button>
            <button 
              className="w-8 h-8 flex items-center justify-center bg-teal-600 text-white rounded-full hover:bg-teal-700 shadow-md transition-colors"
              onClick={() => setIsPlaying(!isPlaying)}
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
            </button>
            <button className="p-1 hover:bg-slate-100 rounded-full transition-colors"><SkipForward className="w-4 h-4" /></button>
          </div>

          <div className="flex-1 flex items-center space-x-4">
            <div className="h-1.5 w-full bg-slate-200 rounded-full overflow-hidden relative cursor-pointer">
              <div className="absolute top-0 left-0 h-full w-[95%] bg-teal-500 rounded-full"></div>
              <div className="absolute top-1/2 -translate-y-1/2 right-[5%] w-3 h-3 bg-white border-2 border-teal-500 rounded-full shadow"></div>
            </div>
          </div>

          <div className="flex items-center space-x-4 shrink-0 font-mono">
            <div className="text-sm font-bold text-slate-800">
              {time.toLocaleTimeString('en-US', { hour12: false })}
            </div>
            <div className="px-2 py-1 bg-slate-100 rounded text-xs font-semibold text-slate-600">
              1x
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
