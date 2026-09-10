import React, { useState } from 'react';
import { 
  AlertOctagon, 
  AlertTriangle, 
  Clock, 
  Send, 
  CheckCircle, 
  ShieldAlert
} from 'lucide-react';

export interface IncidentItem {
  id: string;
  // SN-012g/§13.10: 'ACCIDENT' was previously a real member of this union, and
  // the seed data below used it. CLAUDE.md §8 documents that the (not yet
  // built — Phase 6, SN-083) Incident model deliberately has no ACCIDENT
  // value, "so the schema itself prevents the overclaim" a false positive
  // would make. This frontend type stays consistent with that constraint.
  type: 'POSSIBLE_INCIDENT' | 'CONGESTION' | 'SLOW_TRAFFIC' | 'OBSTACLE';
  severity: 'CRITICAL' | 'HIGH' | 'WARNING';
  title: string;
  location: string;
  timestamp: string;
  confidence: number;
  action: string;
  status: 'PENDING' | 'DISPATCHED' | 'RESOLVED';
}

// SN-012g: this component previously seeded four hardcoded incidents —
// including one typed ACCIDENT with a fabricated confidence score and a
// scripted "Dispatch Ambulance" action — rendered permanently as if live,
// with no WS/API call anywhere in this file. Phase 6 (Incident System,
// SN-083+) hasn't been built yet: there is no detector and no data model.
// Starts empty; wire this to a real incidents feed once one exists.
export const LiveIncidents: React.FC = () => {
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [filter, setFilter] = useState<'ALL' | 'CRITICAL' | 'HIGH' | 'WARNING'>('ALL');

  const handleAction = (id: string) => {
    setIncidents((prev) =>
      prev.map((inc) =>
        inc.id === id ? { ...inc, status: inc.status === 'PENDING' ? 'DISPATCHED' : 'RESOLVED' } : inc
      )
    );
  };

  const filtered = filter === 'ALL' ? incidents : incidents.filter((i) => i.severity === filter);

  return (
    <div className="bg-white rounded-3xl p-6 border border-studio-pink/40 shadow-studio-card relative font-syne">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-studio-pink/30">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-studio-coral animate-ping" />
            <span className="font-mono text-xs font-bold text-studio-coral uppercase tracking-wider">
              ROAD SAFETY INCIDENT MONITOR
            </span>
          </div>
          <h3 className="text-xl font-black text-studio-text mt-1 flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-studio-coral" />
            Live Incident Stream & Dispatch
          </h3>
        </div>

        {/* Severity Filter Pills */}
        <div className="flex items-center gap-1.5 bg-studio-bgLight p-1.5 rounded-full border border-studio-pink/40 font-grotesk">
          {(['ALL', 'CRITICAL', 'HIGH', 'WARNING'] as const).map((sev) => (
            <button
              key={sev}
              onClick={() => setFilter(sev)}
              className={`px-3.5 py-1 rounded-full text-xs font-bold transition-all ${
                filter === sev
                  ? 'bg-studio-coral text-white shadow-sm'
                  : 'text-studio-text/70 hover:text-studio-coral'
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Incidents Cards Grid */}
      {filtered.length === 0 && (
        <div className="my-6 py-8 text-center text-sm text-studio-muted font-grotesk">
          No incident detection system connected yet.
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 my-6 font-grotesk">
        {filtered.map((item) => {
          const isCritical = item.severity === 'CRITICAL';
          const isHigh = item.severity === 'HIGH';

          return (
            <div
              key={item.id}
              className={`p-5 rounded-2xl border transition-all duration-300 relative overflow-hidden flex flex-col justify-between ${
                isCritical
                  ? 'bg-red-50/70 border-red-200 hover:border-red-300'
                  : isHigh
                  ? 'bg-amber-50/70 border-amber-200 hover:border-amber-300'
                  : 'bg-studio-bgLight/60 border-studio-pink/30 hover:border-studio-pink/60'
              }`}
            >
              {/* Card top */}
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    {isCritical ? (
                      <span className="p-1.5 rounded-full bg-red-100 text-red-600 border border-red-200">
                        <AlertOctagon className="w-4 h-4" />
                      </span>
                    ) : (
                      <span className="p-1.5 rounded-full bg-amber-100 text-amber-600 border border-amber-200">
                        <AlertTriangle className="w-4 h-4" />
                      </span>
                    )}
                    <span className={`text-xs font-mono font-black tracking-wider ${
                      isCritical ? 'text-red-700' : isHigh ? 'text-amber-800' : 'text-studio-text'
                    }`}>
                      {item.title}
                    </span>
                  </div>

                  {/* Status badge */}
                  <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full font-bold ${
                    item.status === 'RESOLVED'
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                      : item.status === 'DISPATCHED'
                      ? 'bg-blue-100 text-blue-800 border border-blue-300'
                      : 'bg-red-100 text-red-700 border border-red-300'
                  }`}>
                    {item.status}
                  </span>
                </div>

                <div className="font-bold text-studio-text text-base mt-2 font-syne">
                  {item.location}
                </div>

                <div className="flex items-center gap-3 text-xs font-mono text-studio-muted mt-1 mb-4">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    {item.timestamp}
                  </span>
                  <span>•</span>
                  <span>CONFIDENCE: <strong className="text-studio-coral">{item.confidence}%</strong></span>
                </div>

                {/* AI Action Box */}
                <div className="bg-white/80 p-3 rounded-xl border border-studio-pink/40 text-xs mb-4 shadow-sm">
                  <div className="text-[10px] font-mono text-studio-coral font-bold uppercase">
                    RECOMMENDED DISPATCH ACTION:
                  </div>
                  <div className="text-studio-text mt-1 leading-snug font-medium">
                    {item.action}
                  </div>
                </div>
              </div>

              {/* Action Button */}
              <div className="pt-3 border-t border-studio-pink/30 flex items-center justify-between">
                <span className="text-[11px] font-mono text-studio-muted">ID: {item.id}</span>
                {item.status === 'RESOLVED' ? (
                  <div className="flex items-center gap-1.5 text-xs text-emerald-700 font-bold">
                    <CheckCircle className="w-4 h-4" />
                    <span>Incident Closed</span>
                  </div>
                ) : (
                  <button
                    onClick={() => handleAction(item.id)}
                    className={`px-4 py-1.5 rounded-full text-xs font-bold font-grotesk uppercase tracking-wider flex items-center gap-1.5 transition-all shadow-sm ${
                      item.status === 'PENDING'
                        ? 'bg-studio-coral hover:bg-studio-coralDark text-white'
                        : 'bg-studio-black hover:bg-slate-900 text-white'
                    }`}
                  >
                    <Send className="w-3 h-3" />
                    <span>{item.status === 'PENDING' ? 'Dispatch Unit' : 'Mark Resolved'}</span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
