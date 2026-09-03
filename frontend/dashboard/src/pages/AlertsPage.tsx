import { useState } from 'react';
import { AlertTriangle, AlertCircle, Info, CheckCircle } from 'lucide-react';
import clsx from 'clsx';

type Severity = 'CRITICAL' | 'WARNING' | 'INFO';

interface Alert {
  id: string;
  type: string;
  severity: Severity;
  message: string;
  junctionId: string;
  timestamp: string;
  acknowledged: boolean;
}

const MOCK_ALERTS: Alert[] = [
  { id: '1', severity: 'CRITICAL', type: 'CONGESTION', message: 'Severe congestion at Junction A4-N. Queue exceeding 200m.', junctionId: 'A4-N', timestamp: '2m ago', acknowledged: false },
  { id: '2', severity: 'WARNING', type: 'SPILLBACK', message: 'Spillback risk at Link 104-B approaching 0.82 threshold.', junctionId: '104-B', timestamp: '5m ago', acknowledged: false },
  { id: '3', severity: 'CRITICAL', type: 'SIGNAL_FAILURE', message: 'Signal controller fault at Junction B-12. Fallback to fixed-time.', junctionId: 'B-12', timestamp: '8m ago', acknowledged: true },
  { id: '4', severity: 'WARNING', type: 'QUEUE_OVERFLOW', message: 'Queue overflow detected at approach W of Junction C-7.', junctionId: 'C-7', timestamp: '15m ago', acknowledged: false },
  { id: '5', severity: 'INFO', type: 'CONGESTION', message: 'Congestion clearing at Junction D-3 after MARL intervention.', junctionId: 'D-3', timestamp: '22m ago', acknowledged: true },
  { id: '6', severity: 'INFO', type: 'CONGESTION', message: 'Normal flow restored on Corridor Alpha.', junctionId: 'ALPHA-1', timestamp: '45m ago', acknowledged: true },
];

const AlertsPage: React.FC = () => {
  const [filter, setFilter] = useState<'ALL' | Severity>('ALL');
  const [showAcknowledged, setShowAcknowledged] = useState(true);

  const filteredAlerts = MOCK_ALERTS.filter(alert => {
    if (filter !== 'ALL' && alert.severity !== filter) return false;
    if (!showAcknowledged && alert.acknowledged) return false;
    return true;
  });

  const getSeverityStyles = (severity: Severity) => {
    switch (severity) {
      case 'CRITICAL': return { icon: AlertTriangle, color: 'text-red-600', bg: 'bg-red-50' };
      case 'WARNING': return { icon: AlertCircle, color: 'text-amber-500', bg: 'bg-amber-50' };
      case 'INFO': return { icon: Info, color: 'text-sky-600', bg: 'bg-sky-50' };
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">System Alerts</h1>
          <p className="text-sm text-slate-500 mt-1">Real-time monitoring & incident tracking</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4 items-center justify-between bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-4">
        <div className="flex gap-2">
          {['ALL', 'CRITICAL', 'WARNING', 'INFO'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f as typeof filter)}
              className={clsx(
                'rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                filter === f
                  ? 'bg-sky-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              )}
            >
              {f === 'ALL' ? 'All' : f.charAt(0) + f.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-slate-600">Show Acknowledged</span>
          <button
            onClick={() => setShowAcknowledged(!showAcknowledged)}
            className={clsx(
              "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
              showAcknowledged ? "bg-sky-600" : "bg-slate-300"
            )}
          >
            <span
              className={clsx(
                "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                showAcknowledged ? "translate-x-6" : "translate-x-1"
              )}
            />
          </button>
        </div>
      </div>

      {/* Alert List */}
      <div className="space-y-4">
        {filteredAlerts.map(alert => {
          const { icon: Icon, color, bg } = getSeverityStyles(alert.severity);
          
          return (
            <div key={alert.id} className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-4 sm:px-6 sm:py-5 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between transition-colors hover:border-slate-300">
              <div className="flex items-start gap-4 flex-1">
                <div className={clsx("p-3 rounded-full mt-1", bg)}>
                  <Icon className={clsx("w-6 h-6", color)} />
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={clsx(
                      "text-xs font-semibold uppercase tracking-wider px-2 py-1 rounded-full",
                      alert.severity === 'CRITICAL' ? 'bg-red-100 text-red-700' :
                      alert.severity === 'WARNING' ? 'bg-amber-100 text-amber-700' :
                      'bg-sky-100 text-sky-700'
                    )}>
                      {alert.type}
                    </span>
                    <span className="font-mono text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded-md">ID: {alert.junctionId}</span>
                    <span className="text-xs text-slate-400">{alert.timestamp}</span>
                  </div>
                  <p className="text-slate-800 text-sm font-medium leading-relaxed">
                    {alert.message}
                  </p>
                </div>
              </div>
              
              <div className="flex-shrink-0 self-end sm:self-center">
                {alert.acknowledged ? (
                  <div className="flex items-center gap-1.5 text-emerald-600 text-sm font-medium px-4 py-2">
                    <CheckCircle className="w-5 h-5" />
                    <span>Acknowledged</span>
                  </div>
                ) : (
                  <button className="rounded-lg px-4 py-2.5 font-medium transition-colors bg-sky-50 text-sky-600 hover:bg-sky-100 border border-sky-200 text-sm">
                    Acknowledge
                  </button>
                )}
              </div>
            </div>
          );
        })}
        {filteredAlerts.length === 0 && (
          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-12 text-center">
            <CheckCircle className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="text-lg font-medium text-slate-900">All clear</h3>
            <p className="text-slate-500">No alerts match your current filters.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default AlertsPage;
