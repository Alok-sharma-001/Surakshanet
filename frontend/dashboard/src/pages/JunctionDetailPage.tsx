import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AlertTriangle, ArrowDown, ArrowLeft, ArrowUp, ArrowRight, Video, ChevronLeft, VideoOff } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { api } from '../services/api';
import { useTrafficStore } from '../store/trafficStore';
import { wsService } from '../services/websocket';
import { TelemetrySourceBadge } from '../components/TelemetrySourceBadge';

type ApproachDirection = 'N' | 'E' | 'S' | 'W';

// SN-012g: real per-approach telemetry only comes through for the four
// simulated corridor junctions (J0-J3), matched by name below via the WS
// 'traffic' channel's JunctionTelemetry. A junction with no live match (any
// DB-seeded junction that isn't part of the running SUMO corridor) shows an
// empty approach list rather than the four-direction fake breakdown this
// page used to render unconditionally (pcu/speed/queue and a vehicle-type
// split invented per direction, none of it backed by any producer).
interface ApproachData {
  direction: ApproachDirection;
  label: string;
  icon: React.ElementType;
  pcu: number;
  queueLength: number;
  speed: number | null; // null when no producer resolved a speed this window (e.g. an uncalibrated vision camera) — never a fabricated 0
}

const DIRECTION_META: Record<ApproachDirection, { label: string; icon: React.ElementType }> = {
  N: { label: 'North Bound', icon: ArrowDown },
  E: { label: 'East Bound', icon: ArrowLeft },
  S: { label: 'South Bound', icon: ArrowUp },
  W: { label: 'West Bound', icon: ArrowRight },
};

export default function JunctionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const storeJunctions = useTrafficStore((state) => state.junctions);
  const [junctionData, setJunctionData] = useState<any>(null);
  const [signalPlan, setSignalPlan] = useState<any>(null);
  const [approaches, setApproaches] = useState<ApproachData[]>([]);
  const [currentPhase, setCurrentPhase] = useState<number | null>(null);
  const [phaseElapsedS, setPhaseElapsedS] = useState<number | null>(null);
  const [cycleLengthS, setCycleLengthS] = useState<number | null>(null);
  const [telemetrySource, setTelemetrySource] = useState<string | null>(null);

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

  // Real per-approach telemetry: the WS 'traffic' channel carries one
  // JunctionTelemetry message per SUMO junction (junction_id = tl id, e.g.
  // "J0"), matched here against this page's junction name.
  useEffect(() => {
    const junc = storeJunctions.find(j => j.id === id);
    if (!junc) return;

    wsService.connect('traffic');
    const unsub = wsService.onMessage('traffic', (data: any) => {
      if (data.junction_id !== junc.name) return;

      setTelemetrySource(data.source ?? null);
      setCurrentPhase(data.current_phase ?? null);
      setPhaseElapsedS(data.phase_elapsed_s ?? null);
      setCycleLengthS(data.cycle_length_s ?? null);

      if (Array.isArray(data.approaches)) {
        setApproaches(
          data.approaches.map((a: any) => ({
            direction: a.direction,
            label: DIRECTION_META[a.direction as ApproachDirection]?.label ?? a.direction,
            icon: DIRECTION_META[a.direction as ApproachDirection]?.icon ?? ArrowDown,
            pcu: a.pcu,
            queueLength: a.queue_length_m,
            speed: a.mean_speed_kmh ?? null,
          }))
        );
      }
    });

    return unsub;
  }, [id, storeJunctions]);

  const handleFlashAllRed = async () => {
    if (!id) return;
    try {
      await api.signals.override(id, "FLASH_ALL_RED");
      toast.success("EMERGENCY ALL-RED override engaged on junction controller!");
    } catch {
      toast.error("Could not reach the junction controller — override not applied.");
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
            <TelemetrySourceBadge source={telemetrySource} />
          </div>
          <p className="text-xs font-mono text-slate-400 mt-1">NODE-ID: {id || "DEL-CP-01"}</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleFlashAllRed}
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

          {/* Camera Feed — SN-004/SN-012g: no worker is wired to this page, so
              this used to render four hardcoded YOLO bounding boxes with fake
              confidence scores over a "CAM_01_FEED_ONLINE" claim. Matching the
              acceptance bar set for ComputerVisionFeed.tsx ("with no worker the
              panel shows 'No video source'"), this shows the same honest state
              until a real vision_worker stream (Phase 5, SN-069+) exists. */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
            <div className="flex justify-between items-center mb-3">
              <div className="flex items-center gap-2">
                <Video className="w-4 h-4 text-slate-400" />
                <h3 className="text-sm font-semibold text-slate-800">Edge Camera Feed</h3>
              </div>
              <TelemetrySourceBadge source={null} showIcon={false} />
            </div>

            <div className="relative bg-slate-900 rounded-xl aspect-video overflow-hidden border border-slate-700 flex items-center justify-center shadow-inner">
              <div className="text-center text-slate-500 text-xs font-mono flex flex-col items-center gap-2">
                <VideoOff className="w-8 h-8 text-slate-600" />
                No video source
              </div>
            </div>
          </div>

          {/* Phase Visualizer — real current_phase/phase_elapsed_s from the WS
              'traffic' feed when this junction is part of the running
              simulation; an honest unavailable state otherwise. Previously
              this ran its own 14s→0→35s countdown loop unconditionally and
              claimed a fixed North/South-green, East/West-red split even
              when nothing was actually driving that junction. */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-800">Adaptive Phase Visualizer</h3>
                <p className="text-xs text-slate-500">Mode: {signalPlan?.mode ?? '—'}</p>
              </div>
              <span className="text-xs font-mono font-bold text-teal-600 bg-teal-50 px-2.5 py-1 rounded">
                Cycle: {cycleLengthS !== null ? `${cycleLengthS}s` : '—'}
              </span>
            </div>

            {currentPhase !== null ? (
              <div className="flex flex-col sm:flex-row items-center justify-around gap-6 py-4 bg-slate-50 rounded-xl border border-slate-100">
                <div className="text-center">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Current Phase</div>
                  <div className="w-24 h-24 rounded-full bg-teal-600 text-white flex flex-col items-center justify-center font-mono shadow-md mx-auto">
                    <span className="text-3xl font-bold">{currentPhase}</span>
                    <span className="text-[9px] uppercase tracking-wider font-bold">
                      {phaseElapsedS !== null ? `${Math.round(phaseElapsedS)}s elapsed` : ''}
                    </span>
                  </div>
                </div>
                <TelemetrySourceBadge source={telemetrySource} />
              </div>
            ) : (
              <div className="py-8 text-center text-sm text-slate-400">
                No live phase data for this junction.
              </div>
            )}
          </div>

        </div>

        {/* Right Col: placeholder for future device telemetry. There is no
            edge/Jetson hardware in this project's architecture (see
            CLAUDE.md §2/§3) — the previous panel here invented a full device
            profile (model, IP, GPU temp, inference latency, memory, MQTT
            ping) with no backing subsystem anywhere. Removed rather than
            badged, since there's no real source to badge it with. */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 flex flex-col items-center justify-center text-center gap-2 min-h-[160px]">
            <TelemetrySourceBadge source={null} />
            <p className="text-xs text-slate-400">
              No edge compute hardware is deployed for this junction.
            </p>
          </div>
        </div>

      </div>

      {/* Bottom Approaches Telemetry */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">Approach Lane Telemetry</h3>
          <TelemetrySourceBadge source={telemetrySource} showIcon={false} />
        </div>
        {approaches.length === 0 ? (
          <p className="text-sm text-slate-400 italic">No live approach telemetry for this junction.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {approaches.map((app) => (
              <div key={app.direction} className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-4 space-y-3">
                <div>
                  <div className="font-bold text-sm text-slate-800">{app.label}</div>
                  <div className="text-[11px] text-slate-400 font-mono">Approach {app.direction}</div>
                </div>

                <div className="flex justify-between items-end">
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase block">Flow</span>
                    <span className="text-xl font-mono font-bold text-slate-900">{Math.round(app.pcu)}</span>
                    <span className="text-xs text-slate-500 ml-1">PCU</span>
                  </div>
                  <div className="text-right text-xs font-mono text-slate-600">
                    <div>Spd: {app.speed !== null ? `${app.speed.toFixed(1)} km/h` : 'unavailable'}</div>
                    <div>Que: {app.queueLength.toFixed(0)}m</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
