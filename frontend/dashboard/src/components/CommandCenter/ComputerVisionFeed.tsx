import { useState, useEffect, useRef } from 'react';
import { Camera, ShieldCheck, Crosshair, Cpu, VideoOff, AlertTriangle, CheckCircle, XCircle, Plus, Layers, Trash2 } from 'lucide-react';

interface DetectionBox {
  id: string;
  label: string;
  confidence: number;
  color: string;
  top: number;
  left: number;
  width: number;
  height: number;
}

interface BehaviorFlagItem {
  id: string;
  flag_type: string;
  camera_id: string;
  track_id: string;
  detected_at: string;
  evidence: Record<string, any>;
  confidence: number;
  status: string;
  note: string;
  resolved_by?: string | null;
}

interface RestrictedZoneItem {
  id: string;
  camera_id: string;
  name: string;
  polygon: [number, number][];
  active_start_time?: string;
  active_end_time?: string;
}

const CAM_FEEDS = [
  { id: 'CAM-01', name: 'Cam 01: North Approach', location: 'Intersection A-102 (Downtown)' },
  { id: 'CAM-02', name: 'Cam 02: Ring Road Flyover', location: 'NH-52 Expressway Hub' },
  { id: 'CAM-03', name: 'Cam 03: Cyber Boulevard', location: 'Sector 4 Junction' },
];

export const ComputerVisionFeed: React.FC = () => {
  const [activeCam, setActiveCam] = useState('CAM-01');
  const [boxes, setBoxes] = useState<DetectionBox[]>([]);
  const [fps, setFps] = useState<number | null>(null);
  const [hasVideoSource, setHasVideoSource] = useState(false);
  const [counts, setCounts] = useState({ cars: 0, buses: 0, bikes: 0, pedestrians: 0 });

  // Behavior Flags State (SN-077, SN-078)
  const [flags, setFlags] = useState<BehaviorFlagItem[]>([]);
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  // Restricted Zones State (SN-079)
  const [zones, setZones] = useState<RestrictedZoneItem[]>([]);
  const [isDrawingZone, setIsDrawingZone] = useState(false);
  const [newZoneName, setNewZoneName] = useState('No Parking Clearway');
  const [newZonePoints, setNewZonePoints] = useState<[number, number][]>([]);
  const [savingZone, setSavingZone] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  // 1. Poll for real vision detections (SN-004, SN-078)
  useEffect(() => {
    let isMounted = true;

    const checkVisionFeed = async () => {
      try {
        const response = await fetch(`/api/v1/vision/detections/latest?cam_id=${activeCam}`);
        if (!response.ok) throw new Error('No active feed');
        const data = await response.json();
        if (isMounted && data && (data.fps !== null || data.timestamp !== null)) {
          setBoxes(Array.isArray(data.detections) ? data.detections : []);
          setFps(data.fps ?? 15.0);
          setHasVideoSource(true);
          if (data.counts) setCounts(data.counts);
        } else if (isMounted) {
          setBoxes([]);
          setFps(null);
          setHasVideoSource(false);
          setCounts({ cars: 0, buses: 0, bikes: 0, pedestrians: 0 });
        }
      } catch {
        if (isMounted) {
          setBoxes([]);
          setFps(null);
          setHasVideoSource(false);
          setCounts({ cars: 0, buses: 0, bikes: 0, pedestrians: 0 });
        }
      }
    };

    checkVisionFeed();
    const interval = setInterval(checkVisionFeed, 3000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [activeCam]);

  // 2. Fetch Behavior Flags for active camera (SN-077)
  const fetchFlags = async () => {
    try {
      const res = await fetch(`/api/v1/vision/flags?camera_id=${activeCam}&limit=20`);
      if (res.ok) {
        const data = await res.json();
        setFlags(Array.isArray(data) ? data : []);
      }
    } catch {
      // Offline/fallback
    }
  };

  useEffect(() => {
    fetchFlags();
    const interval = setInterval(fetchFlags, 4000);
    return () => clearInterval(interval);
  }, [activeCam]);

  // 3. Fetch Restricted Zones for active camera (SN-079)
  const fetchZones = async () => {
    try {
      const res = await fetch(`/api/v1/vision/zones?camera_id=${activeCam}`);
      if (res.ok) {
        const data = await res.json();
        setZones(Array.isArray(data) ? data : []);
      }
    } catch {
      // Offline
    }
  };

  useEffect(() => {
    fetchZones();
  }, [activeCam]);

  // 4. Operator Human Gate: Resolve or Dismiss Suspicion Flag (SN-077)
  const handleResolveFlag = async (flagId: string, newStatus: 'CONFIRMED' | 'DISMISSED') => {
    setResolvingId(flagId);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`/api/v1/vision/flags/${flagId}/resolve`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          status: newStatus,
          note: `Operator ${newStatus.toLowerCase()} via CV panel`,
        }),
      });
      if (res.ok) {
        await fetchFlags();
      }
    } catch {
      // Log or toast error
    } finally {
      setResolvingId(null);
    }
  };

  // 5. Zone Drawing Handler (SN-079)
  const handleCanvasClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDrawingZone || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const x = Math.round(((e.clientX - rect.left) / rect.width) * 1280);
    const y = Math.round(((e.clientY - rect.top) / rect.height) * 720);
    setNewZonePoints((prev) => [...prev, [x, y]]);
  };

  const handleSaveZone = async () => {
    if (newZonePoints.length < 3) return;
    setSavingZone(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('/api/v1/vision/zones', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          camera_id: activeCam,
          name: newZoneName,
          polygon: newZonePoints,
          active_start_time: '08:00',
          active_end_time: '20:00',
        }),
      });
      if (res.ok) {
        setNewZonePoints([]);
        setIsDrawingZone(false);
        await fetchZones();
      }
    } catch {
      // Handle error
    } finally {
      setSavingZone(false);
    }
  };

  return (
    <div className="bg-white rounded-3xl p-6 border border-studio-pink/40 shadow-studio-card relative overflow-hidden flex flex-col font-syne">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-studio-pink/30">
        <div>
          <div className="flex items-center gap-2">
            {hasVideoSource ? (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                <span className="font-mono text-xs font-bold text-emerald-700 uppercase tracking-wider">
                  AI ANALYSIS ACTIVE
                </span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-slate-400" />
                <span className="font-mono text-xs font-bold text-slate-500 uppercase tracking-wider">
                  NO VIDEO SOURCE
                </span>
              </>
            )}
            <span className="text-studio-muted">|</span>
            <span className="font-mono text-xs text-studio-muted">YOLOv8n-Real-CV</span>
          </div>
          <h3 className="text-xl font-black text-studio-text mt-1 flex items-center gap-2">
            <Camera className="w-5 h-5 text-studio-coral" />
            Computer Vision Telemetry Feed
          </h3>
        </div>

        {/* Camera Selector Buttons & Zone Editor Toggle */}
        <div className="flex items-center gap-2 flex-wrap font-grotesk">
          <button
            onClick={() => {
              setIsDrawingZone(!isDrawingZone);
              setNewZonePoints([]);
            }}
            className={`px-3 py-1.5 rounded-full text-xs font-bold font-mono transition-all flex items-center gap-1.5 ${
              isDrawingZone
                ? 'bg-amber-600 text-white shadow-sm'
                : 'bg-studio-bgLight text-studio-text/80 border border-studio-pink/50 hover:text-studio-coral'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            {isDrawingZone ? 'Cancel Zone Draw' : 'Restricted Zones'}
          </button>

          {CAM_FEEDS.map((cam) => (
            <button
              key={cam.id}
              onClick={() => {
                setActiveCam(cam.id);
                setIsDrawingZone(false);
                setNewZonePoints([]);
              }}
              className={`px-3.5 py-1.5 rounded-full text-xs font-bold font-mono transition-all ${
                activeCam === cam.id
                  ? 'bg-studio-coral text-white shadow-sm'
                  : 'bg-studio-bgLight text-studio-text/70 border border-studio-pink/40 hover:text-studio-coral'
              }`}
            >
              {cam.id}
            </button>
          ))}
        </div>
      </div>

      {/* Main Grid: Video Stream + Behaviour Flags Side Panel */}
      <div className="my-5 grid grid-cols-1 lg:grid-cols-3 gap-5 items-start">
        {/* Left 2 Cols: Video Stream Container */}
        <div
          ref={containerRef}
          onClick={handleCanvasClick}
          className={`lg:col-span-2 relative w-full h-80 sm:h-96 rounded-2xl bg-studio-bgLight overflow-hidden border border-studio-pink/50 shadow-inner group flex items-center justify-center ${
            isDrawingZone ? 'cursor-crosshair ring-2 ring-amber-500' : ''
          }`}
        >
          {/* Background perspective */}
          <div className="absolute inset-0 bg-gradient-to-b from-studio-pink/20 via-studio-bg/40 to-white/90 flex items-center justify-center pointer-events-none">
            <div className="w-full h-full opacity-15 bg-[radial-gradient(#e5584d_1px,transparent_1px)] [background-size:24px_24px]" />
            <div className="absolute inset-0 flex justify-center pointer-events-none">
              <div className="w-3/4 h-full border-x-2 border-studio-pink/40 transform perspective-[400px] rotate-x-[35deg] bg-white/40" />
            </div>
          </div>

          {/* SVG Overlay for Restricted Zones (SN-079) */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 1280 720" preserveAspectRatio="none">
            {zones.map((z) => (
              <polygon
                key={z.id}
                points={z.polygon.map(([x, y]) => `${x},${y}`).join(' ')}
                fill="rgba(239, 68, 68, 0.15)"
                stroke="#ef4444"
                strokeWidth="2"
                strokeDasharray="4 2"
              />
            ))}
            {/* Active Drawing Polygon */}
            {newZonePoints.length >= 2 && (
              <polygon
                points={newZonePoints.map(([x, y]) => `${x},${y}`).join(' ')}
                fill="rgba(245, 158, 11, 0.2)"
                stroke="#f59e0b"
                strokeWidth="2"
              />
            )}
          </svg>

          {/* Bounding Boxes (Real Detections Only) */}
          {boxes.map((box) => (
            <div
              key={box.id}
              className="absolute transition-all duration-200 pointer-events-none font-grotesk"
              style={{
                top: `${box.top}%`,
                left: `${box.left}%`,
                width: `${box.width}%`,
                height: `${box.height}%`,
              }}
            >
              <div
                className="w-full h-full rounded-lg border-2 relative"
                style={{ borderColor: box.color, boxShadow: `0 0 10px ${box.color}30` }}
              >
                <div className="absolute -top-1 -left-1 w-2 h-2 border-t-2 border-l-2 border-white" />
                <div className="absolute -top-1 -right-1 w-2 h-2 border-t-2 border-r-2 border-white" />
                <div className="absolute -bottom-1 -left-1 w-2 h-2 border-b-2 border-l-2 border-white" />
                <div className="absolute -bottom-1 -right-1 w-2 h-2 border-b-2 border-r-2 border-white" />

                <div
                  className="absolute -top-5 left-0 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold tracking-wider text-white flex items-center gap-1 shadow-sm whitespace-nowrap"
                  style={{ backgroundColor: box.color }}
                >
                  <span>{box.label}</span>
                  <span className="opacity-90">· {box.confidence}%</span>
                </div>
              </div>
            </div>
          ))}

          {/* Explicit "No video source" state overlay */}
          {!hasVideoSource && (
            <div className="relative z-10 flex flex-col items-center justify-center p-6 text-center max-w-sm">
              <div className="w-14 h-14 rounded-2xl bg-studio-pink/30 flex items-center justify-center text-studio-muted mb-3 border border-studio-pink/50">
                <VideoOff className="w-7 h-7 text-slate-500" />
              </div>
              <h4 className="text-base font-bold text-studio-text mb-1">No video source</h4>
              <p className="text-xs text-studio-muted font-grotesk leading-relaxed">
                Camera feed for <span className="font-mono font-bold text-studio-coral">{activeCam}</span> is offline.
                Telemetry detections stream once the vision worker is active.
              </p>
            </div>
          )}

          {/* HUD Camera Overlays */}
          <div className="absolute top-3 left-3 bg-white/95 backdrop-blur-md px-3 py-1.5 rounded-full border border-studio-pink/50 text-[11px] font-mono text-studio-text flex items-center gap-2 shadow-sm">
            <span className={`w-2 h-2 rounded-full ${hasVideoSource ? 'bg-studio-coral animate-pulse' : 'bg-slate-400'}`} />
            <span className="font-bold">{hasVideoSource ? 'LIVE' : 'OFFLINE'}</span>
            <span className="text-studio-coralDark font-bold">{activeCam}</span>
            <span className="text-studio-muted">•</span>
            <span>15 FPS TARGET</span>
          </div>

          <div className="absolute top-3 right-3 bg-white/95 backdrop-blur-md px-3 py-1.5 rounded-full border border-studio-pink/50 text-[11px] font-mono text-studio-text flex items-center gap-3 shadow-sm">
            <div>FPS: <span className="text-emerald-700 font-bold">{fps !== null ? fps : '--'}</span></div>
          </div>

          <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-20">
            <Crosshair className="w-20 h-20 text-studio-coral" />
          </div>

          {/* Bottom Bar: Detected Classes Bar */}
          <div className="absolute bottom-3 left-3 right-3 bg-white/95 backdrop-blur-md px-4 py-2 rounded-2xl border border-studio-pink/50 flex flex-wrap items-center justify-between text-xs font-mono shadow-sm">
            <div className="text-studio-muted flex items-center gap-2 font-semibold">
              <Cpu className="w-3.5 h-3.5 text-studio-coral" />
              <span>CLASSIFICATION BREAKDOWN:</span>
            </div>
            <div className="flex items-center gap-4 text-studio-text font-bold">
              <div>CARS: <span className="text-studio-coral">{counts.cars}</span></div>
              <div>BUSES: <span className="text-slate-800">{counts.buses}</span></div>
              <div>BIKES: <span className="text-amber-600">{counts.bikes}</span></div>
              <div>PEDESTRIANS: <span className="text-emerald-600">{counts.pedestrians}</span></div>
            </div>
          </div>
        </div>

        {/* Right Col: Suspicious Behavior Flags Side List (SN-077, SN-078) */}
        <div className="w-full flex flex-col h-80 sm:h-96 bg-studio-bgLight/60 rounded-2xl border border-studio-pink/40 p-4 overflow-hidden font-grotesk">
          <div className="flex items-center justify-between pb-3 border-b border-studio-pink/30">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <h4 className="text-sm font-bold text-studio-text">Behavior Suspicion Flags</h4>
            </div>
            <span className="text-xs font-mono font-bold bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full">
              {flags.length} total
            </span>
          </div>

          {/* Flag Items List */}
          <div className="flex-1 overflow-y-auto space-y-2.5 py-2.5 pr-1">
            {flags.length === 0 ? (
              <div className="text-xs text-studio-muted text-center py-10 font-grotesk">
                No active behavior suspicion flags recorded on {activeCam}.
              </div>
            ) : (
              flags.map((f) => (
                <div
                  key={f.id}
                  className="bg-white rounded-xl p-3 border border-studio-pink/40 shadow-sm flex flex-col gap-2 text-xs"
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="font-bold text-studio-coralDark tracking-wide font-mono">
                      {f.flag_type.replace('_', ' ')}
                    </span>
                    <span
                      className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${
                        f.status === 'CONFIRMED'
                          ? 'bg-red-100 text-red-800 border border-red-300'
                          : f.status === 'DISMISSED'
                          ? 'bg-slate-100 text-slate-700'
                          : 'bg-amber-100 text-amber-800 border border-amber-300'
                      }`}
                    >
                      {f.status}
                    </span>
                  </div>

                  <div className="text-[11px] text-studio-text/80 space-y-0.5 font-mono">
                    <div>Track ID: <span className="font-bold">{f.track_id}</span></div>
                    {f.evidence?.heading_delta_deg && (
                      <div>Heading Delta: <span className="font-bold">{f.evidence.heading_delta_deg}°</span></div>
                    )}
                    {f.evidence?.dwell_s && (
                      <div>Dwell: <span className="font-bold">{f.evidence.dwell_s}s</span> (in {f.evidence.zone_name})</div>
                    )}
                    {f.evidence?.proxies_exceeded && (
                      <div>Proxies: <span className="font-bold">{f.evidence.proxies_exceeded.join(', ')}</span></div>
                    )}
                  </div>

                  <p className="text-[10px] italic text-studio-muted">{f.note}</p>

                  {/* Operator Human Gate Action Buttons */}
                  {f.status === 'UNVERIFIED' && (
                    <div className="flex items-center justify-end gap-2 pt-1 border-t border-slate-100">
                      <button
                        disabled={resolvingId === f.id}
                        onClick={() => handleResolveFlag(f.id, 'DISMISSED')}
                        className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-[11px] font-bold flex items-center gap-1 transition-all"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        Dismiss
                      </button>
                      <button
                        disabled={resolvingId === f.id}
                        onClick={() => handleResolveFlag(f.id, 'CONFIRMED')}
                        className="px-2.5 py-1 rounded-lg bg-red-600 hover:bg-red-700 text-white text-[11px] font-bold flex items-center gap-1 transition-all shadow-xs"
                      >
                        <CheckCircle className="w-3.5 h-3.5" />
                        Confirm
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Restricted-Zone Editor Tool Drawer (SN-079) */}
      {isDrawingZone && (
        <div className="mb-4 bg-amber-50/70 border border-amber-300 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-grotesk">
          <div className="flex flex-col gap-1">
            <span className="font-bold text-amber-900 flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-amber-700" />
              Draw Restricted Zone on Camera Feed: Click 3+ points on the preview canvas
            </span>
            <span className="text-amber-800 text-[11px]">
              Points recorded: {newZonePoints.length}. Vehicles dwelling &gt;180s inside will be flagged.
            </span>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newZoneName}
              onChange={(e) => setNewZoneName(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-amber-300 bg-white text-xs font-medium"
              placeholder="Zone Name"
            />
            <button
              onClick={() => setNewZonePoints([])}
              className="p-1.5 rounded-lg text-slate-500 hover:bg-amber-100"
              title="Clear Points"
            >
              <Trash2 className="w-4 h-4" />
            </button>
            <button
              disabled={savingZone || newZonePoints.length < 3}
              onClick={handleSaveZone}
              className="px-3.5 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-bold text-xs shadow-sm flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              Save Zone
            </button>
          </div>
        </div>
      )}

      {/* Telemetry Footer */}
      <div className="flex flex-wrap items-center justify-between text-xs text-studio-muted font-mono pt-2 border-t border-studio-pink/30">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          <span>Edge Precision: <strong className="text-studio-text font-bold">NOT MEASURED</strong></span>
          <span className="text-studio-muted">|</span>
          <span>ANPR: <strong className="text-slate-600">DISABLED (PRIVACY BY DEFAULT)</strong></span>
        </div>
        <div>
          LOCATION: <span className="text-studio-text font-semibold">New Delhi Central Operations Matrix</span>
        </div>
      </div>
    </div>
  );
};
