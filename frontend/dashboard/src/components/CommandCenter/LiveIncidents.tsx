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
  type: 'ACCIDENT' | 'CONGESTION' | 'SLOW_TRAFFIC' | 'OBSTACLE';
  severity: 'CRITICAL' | 'HIGH' | 'WARNING';
  title: string;
  location: string;
  timestamp: string;
  confidence: number;
  action: string;
  status: 'PENDING' | 'DISPATCHED' | 'RESOLVED';
}

const INITIAL_INCIDENTS: IncidentItem[] = [
  {
    id: 'INC-901',
    type: 'ACCIDENT',
    severity: 'CRITICAL',
    title: 'ACCIDENT DETECTED',
    location: 'NH-52 · Intersection 08 (Northbound)',
    timestamp: 'Just now (14:42:10)',
    confidence: 96.4,
    action: 'Dispatch Ambulance & Activate Emergency Green Corridor on Links 4-8',
    status: 'PENDING',
  },
  {
    id: 'INC-884',
    type: 'CONGESTION',
    severity: 'HIGH',
    title: 'HEAVY CONGESTION',
    location: 'MG Road · Lane 03 (CBD Core)',
    timestamp: '3m ago (14:39:15)',
    confidence: 89.2,
    action: 'Extend signal green phase by +18s and reroute to Sector 4 Bypass',
    status: 'PENDING',
  },
  {
    id: 'INC-872',
    type: 'SLOW_TRAFFIC',
    severity: 'WARNING',
    title: 'SLOW TRAFFIC FLOW',
    location: 'Ring Road · Sector 4 Flyover Underpass',
    timestamp: '8m ago (14:34:02)',
    confidence: 94.0,
    action: 'Broadcast Variable Message Sign (VMS): "USE ALT ROUTE - BETA RING"',
    status: 'DISPATCHED',
  },
  {
    id: 'INC-850',
    type: 'OBSTACLE',
    severity: 'WARNING',
    title: 'STALLED VEHICLE DETECTED',
    location: 'Sarita Vihar Crossing · Lane 01',
    timestamp: '15m ago (14:27:50)',
    confidence: 98.1,
    action: 'Traffic police patrol dispatched; Lane clearance advisory active',
    status: 'RESOLVED',
  },
];

export const LiveIncidents: React.FC = () => {
  const [incidents, setIncidents] = useState<IncidentItem[]>(INITIAL_INCIDENTS);
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
