import { useState, useEffect, useCallback } from 'react';
import {
  Plus,
  Play,
  Send,
  XCircle,
  Users,
  Layers,
  Check
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import { api } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { TelemetrySourceBadge } from '../components/TelemetrySourceBadge';

interface DemandTranslation {
  expected_crowd: number;
  trips_by_mode: {
    two_wheeler: number;
    car: number;
    auto: number;
    bus: number;
    walk_other: number;
  };
  total_vehicle_trips: number;
  total_pcu: number;
  assumptions: Record<string, unknown>;
}

interface EventItem {
  id: string;
  name: string;
  event_type: string;
  starts_at: string;
  ends_at: string;
  expected_crowd: number;
  affected_links: string[];
  closure_links: string[];
  intensity: string;
  status: 'DRAFT' | 'PREDICTED' | 'APPROVED' | 'PUBLISHED' | 'CANCELLED' | 'CLOSED';
  created_at: string;
  demand_translation?: DemandTranslation;
}

interface LinkDelta {
  link_id: string;
  corridor_name: string;
  baseline_travel_time_s: number;
  event_travel_time_s: number;
  delta_travel_time_s: number;
  delta_pct: number;
  baseline_delay_s: number;
  event_delay_s: number;
  baseline_queue_m: number;
  event_queue_m: number;
  baseline_throughput: number;
  event_throughput: number;
  severity: 'LOW' | 'MODERATE' | 'SEVERE';
}

interface AlternativeRoute {
  rank: number;
  route_text: string;
  edges: string[];
  added_distance_km: number;
  added_time_s: number;
  congestion: string;
  reason: string;
}

interface PredictionData {
  event_id: string;
  computed_at: string;
  source: string;
  seed: number;
  severity_summary: {
    LOW: number;
    MODERATE: number;
    SEVERE: number;
  };
  link_deltas: LinkDelta[];
  alternatives: AlternativeRoute[];
  demand_injection?: {
    assumed_vehicle_trips: number;
    injected_vehicle_trips: number;
    demand_capped: boolean;
  } | null;
}

// Real SUMO corridor edge ids, matching shared/corridor_topology.py exactly —
// a selection here must correspond to an actual edge or closures/injections
// silently no-op in run_whatif_world() (conn.edge.setDisallowed only acts on
// edge ids that exist in the network).
const AVAILABLE_EDGES = [
  { id: 'E_W_to_J0', name: 'West Expressway Entry → Corridor Junction 0' },
  { id: 'E_J0_to_J1', name: 'Corridor Junction 0 → Corridor Junction 1' },
  { id: 'E_J1_to_J0', name: 'Corridor Junction 1 → Corridor Junction 0' },
  { id: 'E_J1_to_J2', name: 'Corridor Junction 1 → Corridor Junction 2' },
  { id: 'E_J2_to_J1', name: 'Corridor Junction 2 → Corridor Junction 1' },
  { id: 'E_J2_to_J3', name: 'Corridor Junction 2 → Corridor Junction 3' },
  { id: 'E_J3_to_J2', name: 'Corridor Junction 3 → Corridor Junction 2' },
  { id: 'E_J3_to_E', name: 'Corridor Junction 3 → East Expressway Exit' },
];

export default function EventsPage() {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'ADMIN';

  const [events, setEvents] = useState<EventItem[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<EventItem | null>(null);
  const [prediction, setPrediction] = useState<PredictionData | null>(null);
  const [isPredicting, setIsPredicting] = useState<boolean>(false);
  const [predictPollActive, setPredictPollActive] = useState<boolean>(false);
  const [filterStatus, setFilterStatus] = useState<string>('ALL');

  // Form state
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [name, setName] = useState<string>('Ganesh Visarjan Procession');
  const [eventType, setEventType] = useState<string>('PROCESSION');
  const [startsAt, setStartsAt] = useState<string>('2026-09-15T16:00');
  const [endsAt, setEndsAt] = useState<string>('2026-09-15T20:00');
  const [expectedCrowd, setExpectedCrowd] = useState<number>(25000);
  const [affectedLinks, setAffectedLinks] = useState<string[]>(['E_J1_to_J2', 'E_J2_to_J3']);
  const [closureLinks, setClosureLinks] = useState<string[]>(['E_J1_to_J2']);
  const [intensity, setIntensity] = useState<string>('HIGH');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Demand calculations derived live
  const calculateDemand = (crowd: number) => {
    const twoWheeler = Math.round((crowd * 0.40) / 1.4);
    const car = Math.round((crowd * 0.25) / 2.1);
    const auto = Math.round((crowd * 0.15) / 2.5);
    const bus = Math.round((crowd * 0.15) / 35.0);
    const totalVehicles = twoWheeler + car + auto + bus;
    return { twoWheeler, car, auto, bus, totalVehicles };
  };

  const demand = calculateDemand(expectedCrowd);

  // Fetch events list
  const fetchEvents = useCallback(async () => {
    try {
      const res = await api.events.getAll(filterStatus === 'ALL' ? undefined : filterStatus);
      if (res.data?.events) {
        setEvents(res.data.events);
        if (res.data.events.length > 0 && !selectedEventId) {
          setSelectedEventId(res.data.events[0].id);
        }
      }
    } catch (err) {
      console.error('Failed to load events', err);
    }
  }, [filterStatus, selectedEventId]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Load single event details and latest prediction
  useEffect(() => {
    if (!selectedEventId) {
      setSelectedEvent(null);
      setPrediction(null);
      return;
    }

    const loadDetails = async () => {
      try {
        const evRes = await api.events.getById(selectedEventId);
        setSelectedEvent(evRes.data);

        // Fetch prediction. The endpoint returns the prediction's fields directly
        // (no nested "prediction" wrapper), and a still-running simulation is a
        // real HTTP 202 with {status: "running"} in the body.
        try {
          const predRes = await api.events.getPrediction(selectedEventId);
          if (predRes.status === 202 || predRes.data?.status === 'running') {
            setIsPredicting(true);
            setPredictPollActive(true);
          } else if (predRes.status === 200 && predRes.data?.status === 'complete') {
            setPrediction(predRes.data);
            setIsPredicting(false);
          }
        } catch (predErr: any) {
          if (predErr.response?.status === 202) {
            setIsPredicting(true);
            setPredictPollActive(true);
          } else {
            setPrediction(null);
            setIsPredicting(false);
          }
        }
      } catch (err) {
        console.error('Error fetching event details', err);
      }
    };

    loadDetails();
  }, [selectedEventId]);

  // Poll prediction when active
  useEffect(() => {
    if (!predictPollActive || !selectedEventId) return;

    const interval = setInterval(async () => {
      try {
        const predRes = await api.events.getPrediction(selectedEventId);
        if (predRes.status === 200 && predRes.data?.status === 'complete') {
          setPrediction(predRes.data);
          setIsPredicting(false);
          setPredictPollActive(false);
          toast.success('Simulation completed! Results ready.');
          fetchEvents();
        }
      } catch (err: any) {
        if (err.response?.status !== 202) {
          setPredictPollActive(false);
          setIsPredicting(false);
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [predictPollActive, selectedEventId, fetchEvents]);

  const handleCreateEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      toast.error('Event name is required');
      return;
    }
    if (affectedLinks.length === 0) {
      toast.error('At least one affected link must be selected');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await api.events.create({
        name,
        event_type: eventType,
        starts_at: new Date(startsAt).toISOString(),
        ends_at: new Date(endsAt).toISOString(),
        expected_crowd: expectedCrowd,
        affected_links: affectedLinks,
        closure_links: closureLinks,
        intensity: intensity,
      });

      toast.success('Event plan created in DRAFT state');
      setShowCreateModal(false);
      await fetchEvents();
      if (res.data?.id) {
        setSelectedEventId(res.data.id);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create event');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRunPrediction = async () => {
    if (!selectedEventId) return;
    setIsPredicting(true);
    setPredictPollActive(true);
    try {
      await api.events.predict(selectedEventId);
      toast.success('Dual-world simulation triggered (Baseline vs Event at Seed 42)');
    } catch (err: any) {
      setIsPredicting(false);
      setPredictPollActive(false);
      toast.error(err.response?.data?.detail || 'Failed to trigger prediction');
    }
  };

  const handleApprove = async () => {
    if (!selectedEventId) return;
    try {
      await api.events.approve(selectedEventId);
      toast.success('Event diversion plan approved by administrator');
      await fetchEvents();
      if (selectedEvent) setSelectedEvent({ ...selectedEvent, status: 'APPROVED' });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Approval failed. Ensure completed prediction exists.');
    }
  };

  const handlePublish = async () => {
    if (!selectedEventId) return;
    try {
      await api.events.publish(selectedEventId);
      toast.success('Advisory published to public surface and logged to audit trail');
      await fetchEvents();
      if (selectedEvent) setSelectedEvent({ ...selectedEvent, status: 'PUBLISHED' });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Publish failed. Admin authorization required.');
    }
  };

  const handleCancel = async () => {
    if (!selectedEventId) return;
    try {
      await api.events.cancel(selectedEventId);
      toast.success('Event cancelled');
      await fetchEvents();
      if (selectedEvent) setSelectedEvent({ ...selectedEvent, status: 'CANCELLED' });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Cancellation failed');
    }
  };

  const toggleLink = (linkId: string, isClosure: boolean) => {
    if (isClosure) {
      if (closureLinks.includes(linkId)) {
        setClosureLinks(closureLinks.filter((id) => id !== linkId));
      } else {
        setClosureLinks([...closureLinks, linkId]);
        if (!affectedLinks.includes(linkId)) {
          setAffectedLinks([...affectedLinks, linkId]);
        }
      }
    } else {
      if (affectedLinks.includes(linkId)) {
        setAffectedLinks(affectedLinks.filter((id) => id !== linkId));
        setClosureLinks(closureLinks.filter((id) => id !== linkId));
      } else {
        setAffectedLinks([...affectedLinks, linkId]);
      }
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'DRAFT':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">DRAFT</span>;
      case 'PREDICTED':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">PREDICTED</span>;
      case 'APPROVED':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">APPROVED</span>;
      case 'PUBLISHED':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">PUBLISHED</span>;
      case 'CANCELLED':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200">CANCELLED</span>;
      default:
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">{status}</span>;
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Event & Rally Traffic Management
            </h1>
            <TelemetrySourceBadge source="SIMULATION" />
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Simulate dual-world what-if scenarios for processions, rallies and public gatherings.
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white rounded-xl text-sm font-semibold shadow-xs transition-colors self-start md:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>New Event Plan</span>
        </button>
      </div>

      {/* Main Grid: Left Event List, Right Event Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Event Selector & Filter (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-xs">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Scheduled Events
              </span>
              <span className="text-xs font-semibold text-slate-400">
                {events.length} plans
              </span>
            </div>

            {/* Filter Pills */}
            <div className="flex gap-1.5 overflow-x-auto pb-2 mb-2 text-xs">
              {['ALL', 'DRAFT', 'PREDICTED', 'APPROVED', 'PUBLISHED'].map((s) => (
                <button
                  key={s}
                  onClick={() => setFilterStatus(s)}
                  className={`px-2.5 py-1 rounded-lg font-medium whitespace-nowrap transition-colors ${
                    filterStatus === s
                      ? 'bg-teal-50 text-teal-700 border border-teal-200'
                      : 'text-slate-500 hover:bg-slate-100'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>

            {/* Events List */}
            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
              {events.length === 0 ? (
                <div className="text-center py-8 text-sm text-slate-400">
                  No events found in this view.
                </div>
              ) : (
                events.map((ev) => (
                  <div
                    key={ev.id}
                    onClick={() => setSelectedEventId(ev.id)}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      selectedEventId === ev.id
                        ? 'border-teal-500 bg-teal-50/50 shadow-xs'
                        : 'border-slate-200 bg-white hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-sm font-bold text-slate-900 leading-snug">
                        {ev.name}
                      </h3>
                      {getStatusBadge(ev.status)}
                    </div>
                    <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
                      <span className="flex items-center gap-1">
                        <Users className="w-3.5 h-3.5" />
                        {ev.expected_crowd.toLocaleString()}
                      </span>
                      <span className="flex items-center gap-1">
                        <Layers className="w-3.5 h-3.5" />
                        {ev.affected_links.length} corridors
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Active Event Workspace (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          {!selectedEvent ? (
            <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center text-slate-400">
              Select an event plan or click &quot;New Event Plan&quot; to begin.
            </div>
          ) : (
            <>
              {/* Event Overview Card */}
              <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-5">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-xl font-bold text-slate-900">
                        {selectedEvent.name}
                      </h2>
                      {getStatusBadge(selectedEvent.status)}
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                      Type: <span className="font-semibold text-slate-700">{selectedEvent.event_type}</span> · Operator Estimate: <span className="font-semibold text-slate-700">{selectedEvent.intensity}</span>
                    </p>
                  </div>

                  {/* Actions Bar */}
                  <div className="flex items-center gap-2 flex-wrap">
                    {(selectedEvent.status === 'DRAFT' || selectedEvent.status === 'PREDICTED') && (
                      <button
                        onClick={handleRunPrediction}
                        disabled={isPredicting}
                        className="flex items-center gap-2 px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-xs disabled:opacity-50 transition-colors"
                      >
                        <Play className={`w-3.5 h-3.5 ${isPredicting ? 'animate-spin' : ''}`} />
                        <span>{isPredicting ? 'Simulating Dual-World...' : 'Run Prediction'}</span>
                      </button>
                    )}

                    {selectedEvent.status === 'PREDICTED' && isAdmin && (
                      <button
                        onClick={handleApprove}
                        className="flex items-center gap-2 px-3.5 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-colors"
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>Approve Plan</span>
                      </button>
                    )}

                    {selectedEvent.status === 'APPROVED' && isAdmin && (
                      <button
                        onClick={handlePublish}
                        className="flex items-center gap-2 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-colors"
                      >
                        <Send className="w-3.5 h-3.5" />
                        <span>Publish Advisory (Gate)</span>
                      </button>
                    )}

                    {selectedEvent.status !== 'CANCELLED' && selectedEvent.status !== 'PUBLISHED' && (
                      <button
                        onClick={handleCancel}
                        className="flex items-center gap-1.5 px-3 py-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-xl text-xs font-medium transition-colors"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        <span>Cancel</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Event Metadata Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                    <span className="text-slate-400 font-medium block">Expected Crowd</span>
                    <span className="text-base font-bold text-slate-900 mt-0.5 block">
                      {selectedEvent.expected_crowd.toLocaleString()}
                    </span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                    <span className="text-slate-400 font-medium block">Affected Links</span>
                    <span className="text-base font-bold text-slate-900 mt-0.5 block">
                      {selectedEvent.affected_links.length} corridors
                    </span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                    <span className="text-slate-400 font-medium block">Full Closures</span>
                    <span className="text-base font-bold text-slate-900 mt-0.5 block">
                      {selectedEvent.closure_links.length} closed
                    </span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                    <span className="text-slate-400 font-medium block">Window</span>
                    <span className="text-xs font-semibold text-slate-800 mt-1 block truncate">
                      {new Date(selectedEvent.starts_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} – {new Date(selectedEvent.ends_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                </div>

                {/* Demand Translation Transparency Box (SN-054) — every number here comes
                    straight from the backend's demand_translation response, never
                    recomputed in the browser. */}
                {selectedEvent.demand_translation ? (
                  <div className="p-4 bg-teal-50/50 border border-teal-200/80 rounded-xl space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5 text-xs font-bold text-teal-900 uppercase tracking-wider">
                        <Users className="w-4 h-4 text-teal-700" />
                        <span>Demand Translation (config.py assumptions)</span>
                      </div>
                      <span className="text-[11px] font-semibold text-teal-700">
                        Total: {selectedEvent.demand_translation.total_vehicle_trips.toLocaleString()} vehicles
                      </span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                      {Object.entries(selectedEvent.demand_translation.trips_by_mode).map(([mode, count]) => (
                        <div key={mode} className="bg-white/80 p-2 rounded-lg border border-teal-100">
                          <span className="text-slate-500 capitalize">{mode.replace(/_/g, ' ')}:</span>
                          <span className="font-bold text-slate-900 ml-1.5">{count.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                    <p className="text-[10px] text-teal-800/80">
                      Formula: Expected Crowd × Mode Share / Vehicle Occupancy (assumptions above, from config.py).
                      {prediction?.demand_injection?.demand_capped && (
                        <>
                          {' '}Simulation injects {prediction.demand_injection.injected_vehicle_trips.toLocaleString()} of these
                          {' '}(capped — the network cannot absorb the full assumed count in one run; severity reflects the capped figure).
                        </>
                      )}
                    </p>
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-400 italic">Demand translation not available for this event.</p>
                )}
              </div>

              {/* Simulation Progress or Results */}
              {isPredicting ? (
                <div className="bg-white border border-blue-200 rounded-2xl p-8 text-center shadow-xs space-y-4">
                  <div className="h-10 w-10 animate-spin rounded-full border-3 border-blue-600 border-t-transparent mx-auto" />
                  <div className="space-y-1">
                    <h3 className="text-base font-bold text-slate-900">
                      Simulating Dual-World What-If Scenarios
                    </h3>
                    <p className="text-xs text-slate-500 max-w-md mx-auto">
                      Executing World A (Baseline) and World B (Event + Closures) in SUMO at Seed 42. Comparing measured travel times and delay deltas.
                    </p>
                  </div>
                </div>
              ) : prediction ? (
                <div className="space-y-6">
                  {/* Severity Summary & Seed Verification */}
                  <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-100 pb-3">
                      <div>
                        <h3 className="text-sm font-bold text-slate-900">
                          Dual-World Impact Assessment (Seed {prediction.seed})
                        </h3>
                        <p className="text-xs text-slate-500">
                          Source: <span className="font-semibold text-slate-700 uppercase">{prediction.source}</span> · Measured at {new Date(prediction.computed_at).toLocaleTimeString()}
                        </p>
                      </div>

                      {/* Severity Legend */}
                      <div className="flex items-center gap-2 text-[11px]">
                        <span className="px-2 py-0.5 rounded bg-red-100 text-red-800 font-semibold">
                          SEVERE &gt;40% ({prediction.severity_summary.SEVERE})
                        </span>
                        <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-semibold">
                          MODERATE 15–40% ({prediction.severity_summary.MODERATE})
                        </span>
                        <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-semibold">
                          LOW &lt;15% ({prediction.severity_summary.LOW})
                        </span>
                      </div>
                    </div>

                    {/* Per-Link Deltas Table */}
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left">
                        <thead>
                          <tr className="border-b border-slate-200 text-slate-400 font-semibold uppercase">
                            <th className="py-2.5 px-3">Corridor</th>
                            <th className="py-2.5 px-3">Baseline TT</th>
                            <th className="py-2.5 px-3">Event TT</th>
                            <th className="py-2.5 px-3">Δ Travel Time</th>
                            <th className="py-2.5 px-3">Delay</th>
                            <th className="py-2.5 px-3">Queue</th>
                            <th className="py-2.5 px-3">Severity</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {prediction.link_deltas.map((link) => (
                            <tr key={link.link_id} className="hover:bg-slate-50 transition-colors">
                              <td className="py-2.5 px-3 font-semibold text-slate-800">
                                <div>{link.corridor_name}</div>
                                <div className="text-[10px] text-slate-400 font-mono">{link.link_id}</div>
                              </td>
                              <td className="py-2.5 px-3 font-mono">{link.baseline_travel_time_s.toFixed(1)}s</td>
                              <td className="py-2.5 px-3 font-mono font-medium text-slate-900">{link.event_travel_time_s.toFixed(1)}s</td>
                              <td className="py-2.5 px-3 font-bold">
                                <span className={
                                  link.severity === 'SEVERE' ? 'text-red-600' :
                                  link.severity === 'MODERATE' ? 'text-amber-600' : 'text-blue-600'
                                }>
                                  +{link.delta_pct.toFixed(1)}% (+{link.delta_travel_time_s.toFixed(1)}s)
                                </span>
                              </td>
                              <td className="py-2.5 px-3 font-mono">{link.event_delay_s.toFixed(1)}s</td>
                              <td className="py-2.5 px-3 font-mono">{link.event_queue_m.toFixed(0)}m</td>
                              <td className="py-2.5 px-3">
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  link.severity === 'SEVERE' ? 'bg-red-100 text-red-800 border border-red-200' :
                                  link.severity === 'MODERATE' ? 'bg-amber-100 text-amber-800 border border-amber-200' :
                                  'bg-blue-100 text-blue-800 border border-blue-200'
                                }`}>
                                  {link.severity}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Alternative Routes Table */}
                  <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-slate-900">
                        Ranked Diversion Alternatives (A* over Event Weights)
                      </h3>
                      <span className="text-xs text-slate-400">
                        {prediction.alternatives.length} options evaluated
                      </span>
                    </div>

                    {prediction.alternatives.length === 0 ? (
                      <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs">
                        No better alternative route found — advising delayed departure.
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {prediction.alternatives.map((alt) => (
                          <div
                            key={alt.rank}
                            className="p-3 rounded-xl border border-slate-200 bg-slate-50 flex items-center justify-between gap-4 text-xs"
                          >
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span className="w-5 h-5 rounded-full bg-teal-600 text-white flex items-center justify-center font-bold text-[10px]">
                                  #{alt.rank}
                                </span>
                                <span className="font-bold text-slate-800">{alt.route_text}</span>
                              </div>
                              <div className="text-slate-500 text-[11px]">{alt.reason}</div>
                            </div>

                            <div className="flex items-center gap-4 shrink-0 text-right">
                              <div>
                                <span className="text-slate-400 block text-[10px]">Added Time</span>
                                <span className="font-bold text-slate-800 font-mono">
                                  +{Math.round(alt.added_time_s / 60)} min ({alt.added_time_s.toFixed(0)}s)
                                </span>
                              </div>
                              <div>
                                <span className="text-slate-400 block text-[10px]">Distance</span>
                                <span className="font-bold text-slate-800 font-mono">+{alt.added_distance_km.toFixed(1)} km</span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="bg-white border border-dashed border-slate-300 rounded-2xl p-8 text-center space-y-2">
                  <Play className="w-8 h-8 text-slate-400 mx-auto" />
                  <p className="text-sm font-semibold text-slate-700">No simulation runs executed yet</p>
                  <p className="text-xs text-slate-400 max-w-sm mx-auto">
                    Click &quot;Run Prediction&quot; to execute the dual-world SUMO simulation and calculate travel time deltas.
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Create Event Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h2 className="text-lg font-bold text-slate-900">Create New Event Plan</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateEvent} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="font-semibold text-slate-700">Event Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    placeholder="e.g. Ganesh Visarjan Procession"
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500 focus:outline-hidden"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-slate-700">Event Type</label>
                  <select
                    value={eventType}
                    onChange={(e) => setEventType(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500 focus:outline-hidden bg-white"
                  >
                    <option value="PROCESSION">Procession</option>
                    <option value="RALLY">Rally</option>
                    <option value="FESTIVAL">Festival</option>
                    <option value="VIP_MOVEMENT">VIP Movement</option>
                    <option value="MARATHON">Marathon</option>
                    <option value="CONCERT">Concert</option>
                    <option value="DEMONSTRATION">Demonstration</option>
                    <option value="GOVERNMENT">Government Function</option>
                    <option value="OTHER">Other</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-slate-700">Starts At (IST)</label>
                  <input
                    type="datetime-local"
                    value={startsAt}
                    onChange={(e) => setStartsAt(e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500 focus:outline-hidden"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-slate-700">Ends At (IST)</label>
                  <input
                    type="datetime-local"
                    value={endsAt}
                    onChange={(e) => setEndsAt(e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500 focus:outline-hidden"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-slate-700">Expected Crowd (Attendees)</label>
                  <input
                    type="number"
                    min="100"
                    step="100"
                    value={expectedCrowd}
                    onChange={(e) => setExpectedCrowd(parseInt(e.target.value) || 0)}
                    required
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500 focus:outline-hidden font-mono"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-slate-700">Operator Intensity Estimate</label>
                  <select
                    value={intensity}
                    onChange={(e) => setIntensity(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500 focus:outline-hidden bg-white"
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                  </select>
                </div>
              </div>

              {/* Demand Translation Display Box in Form */}
              <div className="p-3 bg-teal-50/70 border border-teal-200 rounded-xl space-y-1.5">
                <div className="flex items-center justify-between text-teal-900 font-bold">
                  <span>Derived Additional Vehicle Trips:</span>
                  <span>{demand.totalVehicles.toLocaleString()} vehicles</span>
                </div>
                <div className="grid grid-cols-4 gap-2 text-[11px] text-slate-600">
                  <div>2-Wheeler: <span className="font-semibold text-slate-900">{demand.twoWheeler.toLocaleString()}</span></div>
                  <div>Car: <span className="font-semibold text-slate-900">{demand.car.toLocaleString()}</span></div>
                  <div>Auto: <span className="font-semibold text-slate-900">{demand.auto.toLocaleString()}</span></div>
                  <div>Bus: <span className="font-semibold text-slate-900">{demand.bus.toLocaleString()}</span></div>
                </div>
              </div>

              {/* Affected & Closed Corridors Selection */}
              <div className="space-y-2">
                <label className="font-semibold text-slate-700 block">
                  Select Affected Corridors & Link Closures
                </label>
                <div className="space-y-2 max-h-48 overflow-y-auto border border-slate-200 rounded-xl p-2.5">
                  {AVAILABLE_EDGES.map((edge) => {
                    const isAffected = affectedLinks.includes(edge.id);
                    const isClosed = closureLinks.includes(edge.id);
                    return (
                      <div
                        key={edge.id}
                        className="flex items-center justify-between p-2 rounded-lg bg-slate-50 hover:bg-slate-100/70 transition-colors"
                      >
                        <div>
                          <span className="font-semibold text-slate-800">{edge.name}</span>
                          <span className="text-[10px] text-slate-400 font-mono ml-2">({edge.id})</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <label className="flex items-center gap-1.5 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={isAffected}
                              onChange={() => toggleLink(edge.id, false)}
                              className="rounded text-teal-600 focus:ring-teal-500"
                            />
                            <span className="text-slate-600">Affected</span>
                          </label>
                          <label className="flex items-center gap-1.5 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={isClosed}
                              onChange={() => toggleLink(edge.id, true)}
                              className="rounded text-red-600 focus:ring-red-500"
                            />
                            <span className="text-red-700 font-medium">Fully Closed</span>
                          </label>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-xl font-semibold shadow-xs disabled:opacity-50"
                >
                  {isSubmitting ? 'Creating...' : 'Save Draft Plan'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
