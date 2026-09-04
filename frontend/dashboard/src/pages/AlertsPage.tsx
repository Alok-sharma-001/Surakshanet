import React, { useState, useEffect } from 'react';
import { AlertTriangle, AlertCircle, Info, CheckCircle, RefreshCw } from 'lucide-react';
import clsx from 'clsx';
import { toast } from 'react-hot-toast';
import { api } from '../services/api';

type Severity = 'CRITICAL' | 'WARNING' | 'INFO';

interface AlertItem {
  id: string;
  junction_id?: string;
  alert_type: string;
  severity: Severity;
  message: string;
  is_acknowledged: boolean;
  created_at: string;
  acknowledged_at?: string;
}

const AlertsPage: React.FC = () => {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'ALL' | Severity>('ALL');
  const [showAcknowledged, setShowAcknowledged] = useState(true);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const res = await api.alerts.getAll();
      if (res.data && Array.isArray(res.data)) {
        setAlerts(res.data);
      }
    } catch (err) {
      console.error("Failed to load alerts from backend", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleAcknowledge = async (id: string) => {
    try {
      await api.alerts.acknowledge(id);
      toast.success("Alert marked as acknowledged");
      setAlerts(prev => prev.map(a => a.id === id ? { ...a, is_acknowledged: true } : a));
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to acknowledge alert");
    }
  };

  const filteredAlerts = alerts.filter(alert => {
    if (filter !== 'ALL' && alert.severity !== filter) return false;
    if (!showAcknowledged && alert.is_acknowledged) return false;
    return true;
  });

  const getSeverityStyles = (severity: Severity) => {
    switch (severity) {
      case 'CRITICAL': return { icon: AlertTriangle, color: 'text-red-600', bg: 'bg-red-50' };
      case 'WARNING': return { icon: AlertCircle, color: 'text-amber-500', bg: 'bg-amber-50' };
      case 'INFO': return { icon: Info, color: 'text-teal-600', bg: 'bg-teal-50' };
      default: return { icon: Info, color: 'text-slate-600', bg: 'bg-slate-50' };
    }
  };

  const totalCount = alerts.length;
  const activeCount = alerts.filter(a => !a.is_acknowledged).length;
  const criticalCount = alerts.filter(a => a.severity === 'CRITICAL' && !a.is_acknowledged).length;
  const resolvedCount = totalCount - activeCount;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold font-syne text-slate-900">System Alerts</h1>
          <p className="text-sm text-slate-500 mt-1">Real-time monitoring & incident tracking from PostgreSQL</p>
        </div>
        <button
          onClick={fetchAlerts}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 shadow-sm transition-colors"
        >
          <RefreshCw className={clsx("w-4 h-4 text-slate-500", loading && "animate-spin")} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-4">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Alerts</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">{totalCount}</div>
        </div>
        <div className="bg-white rounded-xl border border-amber-200 bg-amber-50/20 shadow-sm p-4">
          <div className="text-xs font-semibold text-amber-700 uppercase tracking-wider">Active Alerts</div>
          <div className="text-2xl font-bold text-amber-700 mt-1">{activeCount}</div>
        </div>
        <div className="bg-white rounded-xl border border-red-200 bg-red-50/20 shadow-sm p-4">
          <div className="text-xs font-semibold text-red-700 uppercase tracking-wider">Critical Unresolved</div>
          <div className="text-2xl font-bold text-red-700 mt-1">{criticalCount}</div>
        </div>
        <div className="bg-white rounded-xl border border-emerald-200 bg-emerald-50/20 shadow-sm p-4">
          <div className="text-xs font-semibold text-emerald-700 uppercase tracking-wider">Resolved</div>
          <div className="text-2xl font-bold text-emerald-700 mt-1">{resolvedCount}</div>
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
                  ? 'bg-teal-600 text-white'
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
              showAcknowledged ? "bg-teal-600" : "bg-slate-300"
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
        {filteredAlerts.length === 0 ? (
          <div className="bg-white rounded-xl border border-[#E2E8F0] p-12 text-center text-slate-500">
            <CheckCircle className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
            <h3 className="font-semibold text-slate-800 text-lg">No Active Alerts</h3>
            <p className="text-sm mt-1">All corridor thresholds are within nominal bounds.</p>
          </div>
        ) : (
          filteredAlerts.map(alert => {
            const { icon: Icon, color, bg } = getSeverityStyles(alert.severity);

            return (
              <div
                key={alert.id}
                className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-4 sm:px-6 sm:py-5 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between transition-colors hover:border-slate-300"
              >
                <div className="flex items-start gap-4 flex-1">
                  <div className={clsx("p-3 rounded-full mt-1 shrink-0", bg)}>
                    <Icon className={clsx("w-6 h-6", color)} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-slate-900">{alert.alert_type}</span>
                      <span className={clsx("text-xs font-bold px-2 py-0.5 rounded-full uppercase", bg, color)}>
                        {alert.severity}
                      </span>
                      {alert.junction_id && (
                        <span className="text-xs font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                          Junction: {alert.junction_id.slice(0, 8)}...
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-slate-700 mt-1">{alert.message}</p>
                    <div className="flex items-center gap-4 text-xs text-slate-400 mt-2 font-mono">
                      <span>{new Date(alert.created_at).toLocaleString()}</span>
                      {alert.is_acknowledged && (
                        <span className="text-emerald-600 flex items-center gap-1">
                          <CheckCircle className="w-3.5 h-3.5" /> Acknowledged
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {!alert.is_acknowledged && (
                  <button
                    onClick={() => handleAcknowledge(alert.id)}
                    className="px-4 py-2 bg-slate-100 hover:bg-teal-50 text-slate-700 hover:text-teal-700 text-sm font-semibold rounded-lg transition-colors shrink-0"
                  >
                    Acknowledge
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default AlertsPage;
