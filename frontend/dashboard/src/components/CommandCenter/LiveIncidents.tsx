import React, { useState, useEffect } from 'react';
import { 
  AlertOctagon, 
  AlertTriangle, 
  Clock, 
  CheckCircle, 
  XCircle,
  ShieldAlert,
  Radio,
  RefreshCw,
  Send
} from 'lucide-react';
import { api } from '../../services/api';
import { wsService } from '../../services/websocket';
import { toast } from 'react-hot-toast';

export interface IndicatorItem {
  id: string;
  indicator: string;
  measured_value: number;
  threshold: number;
  fired_at: string;
}

export interface IncidentItem {
  id: string;
  incident_type: 'POSSIBLE_INCIDENT';
  status: 'DETECTED' | 'UNVERIFIED' | 'UNDER_REVIEW' | 'CONFIRMED' | 'DISMISSED' | 'RESPONDING' | 'RESOLVED' | 'CLOSED';
  link_id: string;
  junction_id?: string;
  detected_at: string;
  confidence: number; // Anomaly score [0..1]
  indicators_fired: number;
  indicators_total: number;
  indicators: IndicatorItem[];
  note: string;
  evidence_ref?: string;
  confirmed_by?: string;
  resolution?: string;
  warning_published_at?: string;
}

export const LiveIncidents: React.FC = () => {
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<'ALL' | 'UNVERIFIED' | 'CONFIRMED' | 'RESOLVED'>('ALL');

  const fetchIncidents = async () => {
    setLoading(true);
    try {
      const res = await api.incidents.getAll();
      if (res.data && Array.isArray(res.data)) {
        setIncidents(res.data);
      }
    } catch (err) {
      console.error("Failed to load incidents", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
    wsService.connect('incidents');
    const unsub = wsService.onMessage('incidents', (msg: any) => {
      if (msg && msg.payload) {
        setIncidents((prev) => {
          const payload = msg.payload.incident || msg.payload;
          if (!payload.id) return prev;
          const idx = prev.findIndex((i) => i.id === payload.id);
          if (idx >= 0) {
            const updated = [...prev];
            updated[idx] = { ...updated[idx], ...payload };
            return updated;
          }
          return [payload, ...prev];
        });
      }
    });

    const interval = setInterval(fetchIncidents, 10000);
    return () => {
      unsub();
      clearInterval(interval);
    };
  }, []);

  // Action handlers
  const handleConfirm = async (id: string) => {
    try {
      await api.incidents.confirm(id);
      toast.success("Incident confirmed (Human Gate 1 passed). Rerouting & unit proposal active.");
      fetchIncidents();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to confirm incident");
    }
  };

  const handleDismiss = async (id: string) => {
    const reason = window.prompt("Reason for dismissal (mandatory for audit):", "False alarm / sensor fluctuation");
    if (!reason || !reason.trim()) return;
    try {
      await api.incidents.dismiss(id, reason.trim());
      toast.success("Incident dismissed and audited.");
      fetchIncidents();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to dismiss incident");
    }
  };

  const handleEscalate = async (id: string) => {
    try {
      await api.incidents.escalate(id);
      toast.success("Incident escalated to Emergency Services.");
      fetchIncidents();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to escalate incident");
    }
  };

  const handlePublishWarning = async (id: string) => {
    if (!window.confirm("Publishing a public warning is IRREVERSIBLE. Are you sure you want to broadcast this advisory to citizens?")) {
      return;
    }
    try {
      await api.incidents.publishWarning(id);
      toast.success("Public advisory broadcasted (Human Gate 2 passed).");
      fetchIncidents();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to publish warning");
    }
  };

  const handleResolve = async (id: string) => {
    const note = window.prompt("Resolution note / action taken:", "Lanes cleared, traffic returned to nominal flow");
    if (note === null) return;
    try {
      await api.incidents.resolve(id, note.trim() || undefined);
      toast.success("Incident resolved and closed.");
      fetchIncidents();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to resolve incident");
    }
  };

  const filtered = filter === 'ALL' 
    ? incidents 
    : incidents.filter((i) => i.status === filter);

  return (
    <div className="bg-white rounded-3xl p-6 border border-studio-pink/40 shadow-studio-card relative font-syne">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-studio-pink/30">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-studio-coral animate-ping" />
            <span className="font-mono text-xs font-bold text-studio-coral uppercase tracking-wider">
              ROAD SAFETY INCIDENT MONITOR (PHASE 6)
            </span>
          </div>
          <h3 className="text-xl font-black text-studio-text mt-1 flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-studio-coral" />
            Live Incident Stream & Verification Gate
          </h3>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchIncidents}
            disabled={loading}
            className="p-2 rounded-full border border-studio-pink/40 hover:bg-studio-bgLight transition-all"
            title="Refresh incidents"
          >
            <RefreshCw className={`w-4 h-4 text-studio-text/70 ${loading ? 'animate-spin' : ''}`} />
          </button>

          {/* Filter Pills */}
          <div className="flex items-center gap-1.5 bg-studio-bgLight p-1.5 rounded-full border border-studio-pink/40 font-grotesk">
            {(['ALL', 'UNVERIFIED', 'CONFIRMED', 'RESOLVED'] as const).map((st) => (
              <button
                key={st}
                onClick={() => setFilter(st)}
                className={`px-3.5 py-1 rounded-full text-xs font-bold transition-all ${
                  filter === st
                    ? 'bg-studio-coral text-white shadow-sm'
                    : 'text-studio-text/70 hover:text-studio-coral'
                }`}
              >
                {st}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Incidents Grid */}
      {filtered.length === 0 && (
        <div className="my-6 py-8 text-center text-sm text-studio-muted font-grotesk">
          {incidents.length === 0 ? "No active incidents detected on monitored corridors." : "No incidents match the selected filter."}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 my-6 font-grotesk">
        {filtered.map((item) => {
          const isUnverified = item.status === 'UNVERIFIED' || item.status === 'DETECTED';
          const isConfirmed = item.status === 'CONFIRMED' || item.status === 'RESPONDING';
          const isResolved = item.status === 'RESOLVED' || item.status === 'CLOSED';
          const isDismissed = item.status === 'DISMISSED';

          return (
            <div
              key={item.id}
              className={`p-5 rounded-2xl border transition-all duration-300 relative overflow-hidden flex flex-col justify-between ${
                isUnverified
                  ? 'bg-amber-50/70 border-amber-300 hover:border-amber-400'
                  : isConfirmed
                  ? 'bg-red-50/70 border-red-300 hover:border-red-400'
                  : 'bg-studio-bgLight/60 border-studio-pink/30'
              }`}
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    {isUnverified ? (
                      <span className="p-1.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200">
                        <AlertTriangle className="w-4 h-4" />
                      </span>
                    ) : (
                      <span className="p-1.5 rounded-full bg-red-100 text-red-600 border border-red-200">
                        <AlertOctagon className="w-4 h-4" />
                      </span>
                    )}
                    <span className="text-xs font-mono font-black tracking-wider text-studio-text">
                      Possible incident — {item.indicators_fired} of {item.indicators_total} indicators
                    </span>
                  </div>

                  {/* Status Badge */}
                  <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full font-bold ${
                    isUnverified
                      ? 'bg-amber-100 text-amber-900 border border-amber-300 animate-pulse'
                      : isConfirmed
                      ? 'bg-red-100 text-red-800 border border-red-300'
                      : isResolved
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                      : 'bg-slate-100 text-slate-700 border border-slate-300'
                  }`}>
                    {item.status}
                  </span>
                </div>

                <div className="font-bold text-studio-text text-base mt-2 font-syne">
                  Link: {item.link_id} {item.junction_id ? `(Junction: ${item.junction_id})` : ''}
                </div>

                <div className="flex items-center gap-3 text-xs font-mono text-studio-muted mt-1 mb-3">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    {new Date(item.detected_at).toLocaleTimeString()}
                  </span>
                  <span>•</span>
                  <span>ANOMALY SCORE: <strong className="text-studio-coral">{Math.round(item.confidence * 100)}%</strong></span>
                </div>

                {/* Measured Indicators Breakdown */}
                <div className="bg-white/90 p-3 rounded-xl border border-studio-pink/30 text-xs mb-3 space-y-1.5">
                  <div className="text-[10px] font-mono text-studio-coral font-bold uppercase">
                    MEASURED ANOMALY INDICATORS:
                  </div>
                  {item.indicators && item.indicators.length > 0 ? (
                    item.indicators.map((ind, idx) => (
                      <div key={idx} className="flex items-center justify-between text-slate-700 font-mono text-[11px]">
                        <span>• {ind.indicator}</span>
                        <span className="font-semibold text-slate-900">
                          {ind.measured_value} (threshold {ind.threshold})
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className="text-slate-500 italic">Evaluating link telemetry...</div>
                  )}
                </div>

                {/* Honesty Note */}
                <div className="text-[11px] text-slate-500 italic mb-4">
                  {item.note}
                </div>
              </div>

              {/* Action Buttons & Human Gates */}
              <div className="pt-3 border-t border-studio-pink/30 flex flex-col gap-2">
                <div className="flex items-center justify-between text-[11px] font-mono text-studio-muted">
                  <span>ID: {item.id.slice(0, 8)}...</span>
                  {item.warning_published_at && (
                    <span className="text-blue-700 font-bold flex items-center gap-1">
                      <Radio className="w-3.5 h-3.5" /> Warning Broadcast Active
                    </span>
                  )}
                </div>

                {/* Gate 1 Controls */}
                {isUnverified && (
                  <div className="flex items-center gap-2 mt-1">
                    <button
                      onClick={() => handleConfirm(item.id)}
                      className="flex-1 px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white flex items-center justify-center gap-1 shadow-sm"
                    >
                      <CheckCircle className="w-3.5 h-3.5" />
                      <span>Confirm (Gate 1)</span>
                    </button>
                    <button
                      onClick={() => handleDismiss(item.id)}
                      className="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-200 hover:bg-slate-300 text-slate-800 flex items-center justify-center gap-1"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Dismiss</span>
                    </button>
                    <button
                      onClick={() => handleEscalate(item.id)}
                      className="px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-500 hover:bg-amber-600 text-white flex items-center justify-center gap-1"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>Escalate</span>
                    </button>
                  </div>
                )}

                {/* Gate 2 Control: Public Warning & Resolution */}
                {isConfirmed && (
                  <div className="flex flex-col gap-2 mt-1">
                    {!item.warning_published_at && (
                      <button
                        onClick={() => handlePublishWarning(item.id)}
                        className="w-full px-3 py-2 rounded-lg text-xs font-bold bg-red-600 hover:bg-red-700 text-white flex items-center justify-center gap-1.5 shadow-sm border border-red-700"
                      >
                        <Radio className="w-3.5 h-3.5 animate-pulse" />
                        <span>Publish Public Warning (Gate 2 — Irreversible)</span>
                      </button>
                    )}
                    <button
                      onClick={() => handleResolve(item.id)}
                      className="w-full px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white flex items-center justify-center gap-1 shadow-sm"
                    >
                      <CheckCircle className="w-3.5 h-3.5" />
                      <span>Resolve Incident</span>
                    </button>
                  </div>
                )}

                {isResolved && (
                  <div className="flex items-center gap-1 text-xs text-emerald-700 font-bold mt-1">
                    <CheckCircle className="w-4 h-4" />
                    <span>Incident Resolved ({item.resolution || 'closed'})</span>
                  </div>
                )}

                {isDismissed && (
                  <div className="flex items-center gap-1 text-xs text-slate-500 font-bold mt-1">
                    <XCircle className="w-4 h-4" />
                    <span>Dismissed: {item.resolution}</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
